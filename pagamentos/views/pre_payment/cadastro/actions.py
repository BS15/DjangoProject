"""Acoes POST da etapa de documentos fiscais do cadastro."""

import logging
from typing import Optional
from datetime import date
import PyPDF2

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import DatabaseError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from decimal import Decimal, InvalidOperation
import json
from django.db.models import Sum
from django.contrib.contenttypes.models import ContentType
from fiscal.models import DocumentoFiscal, RetencaoImposto, StatusChoicesRetencoes
from commons.shared.text_tools import normalize_text
from pagamentos.domain_models import (
    Boleto_Bancario,
    DocumentoProcesso,
    TiposDePendencias,
    StatusChoicesPendencias,
    Pendencia,
    Processo,
    ProcessoStatus,
)
from .helpers import processar_pdf_boleto
from .forms import DocumentoFormSet, DocumentoOrcamentarioFormSet, PendenciaFormSet, ProcessoCapaEdicaoForm, ProcessoForm
from ..helpers import (
    _redirect_seguro_ou_fallback,
    _salvar_processo_completo,
    _validar_regras_edicao_processo,
)


logger = logging.getLogger(__name__)

PENDENCIA_ACAO_STATUS = {
    "resolver": "RESOLVIDO",
    "excluir": "EXCLUÍDO",
}


def _documento_eh_boleto_bancario(documento: DocumentoProcesso) -> bool:
    """Indica se o tipo documental corresponde a BOLETO BANCÁRIO."""
    if not documento.tipo:
        return False
    return normalize_text(documento.tipo.tipo_documento) == "BOLETO BANCARIO"


def _mensagens_validacao_formset_documentos(documento_formset: DocumentoFormSet) -> list[str]:
    """Consolida erros do formset em mensagens amigáveis por linha/campo."""
    mensagens = []

    non_form_errors = [str(err) for err in documento_formset.non_form_errors()]
    mensagens.extend(non_form_errors)

    for idx, form in enumerate(documento_formset.forms, start=1):
        if not form.errors:
            continue

        for campo, erros in form.errors.items():
            rotulo_campo = "linha" if campo == "__all__" else campo
            erros_linha = "; ".join(str(erro) for erro in erros)
            mensagens.append(f"Documento {idx} - {rotulo_campo}: {erros_linha}")

    return mensagens


def _get_status_inicial(processo):
    return processo.status.opcao_status.upper() if processo.status else ""


def _obter_contexto_edicao(request: HttpRequest, pk: int) -> tuple[Processo, str, Optional[HttpResponse], bool]:
    processo = get_object_or_404(Processo, id=pk)
    status_inicial = _get_status_inicial(processo)
    redirecionamento, somente_documentos = _validar_regras_edicao_processo(request, processo, status_inicial)
    return processo, status_inicial, redirecionamento, somente_documentos


def _salvar_formsets_em_transacao(*formsets):
    with transaction.atomic():
        for formset in formsets:
            formset.save()


def _status_bloqueia_exclusao_nota_fiscal(processo):
    """Indica se o processo já está em estágio onde exclusão de nota é proibida."""
    return _status_bloqueia_gestao_fiscal(processo)


def _status_bloqueia_gestao_fiscal(processo):
    """Bloqueia gestão fiscal no pós-pagamento, exceto quando há contingência ativa."""
    if processo.em_contingencia:
        return False

    if not processo.status:
        return False

    status_atual = (processo.status.opcao_status or "").upper()
    return status_atual in {
        ProcessoStatus.PAGO_EM_CONFERENCIA,
        ProcessoStatus.PAGO_A_CONTABILIZAR,
        ProcessoStatus.CONTABILIZADO_CONSELHO,
        ProcessoStatus.APROVADO_PENDENTE_ARQUIVAMENTO,
        ProcessoStatus.ARQUIVADO,
    }


def _atualizar_status_pendencia(pendencia: Pendencia, status_destino: str) -> None:
    """Atualiza o status da pendência com criação lazy do catálogo quando necessário."""
    status_obj, _ = StatusChoicesPendencias.objects.get_or_create(
        opcao_status__iexact=status_destino,
        defaults={"opcao_status": status_destino},
    )
    pendencia.status = status_obj
    pendencia.save(update_fields=["status"])


@require_POST
@permission_required("pagamentos.acesso_backoffice", raise_exception=True)
def add_process_action(request: HttpRequest) -> HttpResponse:
    """Persiste a capa inicial do processo."""
    processo_form = ProcessoForm(request.POST, prefix="processo")
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER", "")
    trigger_a_empenhar = request.POST.get("trigger_a_empenhar") == "on"

    if not processo_form.is_valid():
        messages.error(request, "Verifique os erros no formulário da capa do processo.")
        return render(
            request,
            "pagamentos/add_process.html",
            {
                "processo_form": processo_form,
                "next_url": next_url,
                "trigger_a_empenhar_checked": trigger_a_empenhar,
            },
            status=400,
        )

    try:
        def mutator(processo_instancia):
            processo_instancia.definir_status_inicial(trigger_a_empenhar)

        processo = _salvar_processo_completo(processo_form, mutator_func=mutator)
        messages.success(
            request,
            f"Processo #{processo.id} inserido com sucesso! Complete documentos, fiscais e pendências na etapa de edição.",
        )
        return _redirect_seguro_ou_fallback(request, next_url, "editar_processo", processo.id)
    except (DatabaseError, TypeError, ValueError):
        logger.exception("Erro crítico ao salvar processo na criação")
        messages.error(request, "Ocorreu um erro interno ao salvar no banco de dados.")
        return redirect("add_process")


@require_POST
@permission_required("pagamentos.acesso_backoffice", raise_exception=True)
def editar_processo_capa_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Persiste alterações da capa do processo."""
    processo, status_inicial, redirecionamento, somente_documentos = _obter_contexto_edicao(request, pk)
    if redirecionamento:
        return redirecionamento
    if somente_documentos:
        messages.error(request, "Neste status, apenas documentos podem ser alterados. Use a tela específica de documentos.")
        return redirect("editar_processo_documentos", pk=pk)

    processo_form = ProcessoCapaEdicaoForm(request.POST, instance=processo, prefix="processo")
    next_url = request.POST.get("next") or ""

    if not processo_form.is_valid():
        messages.error(request, "Verifique os erros na capa do processo.")
        return redirect("editar_processo_capa", pk=pk)

    confirmar_extra = request.POST.get("confirmar_extra_orcamentario") == "on"
    try:
        def _mutator(proc):
            proc.converter_para_extraorcamentario(confirmar_extra)

        processo_saved = _salvar_processo_completo(processo_form, mutator_func=_mutator)
        messages.success(request, f"Capa do Processo #{processo_saved.id} atualizada com sucesso!")
        return _redirect_seguro_ou_fallback(request, next_url, "editar_processo", processo_saved.id)
    except (DatabaseError, TypeError, ValueError):
        logger.exception("Erro ao atualizar capa do processo %s", pk)
        messages.error(request, "Erro interno ao salvar a capa do processo.")
        return redirect("editar_processo_capa", pk=pk)


@require_POST
@permission_required("pagamentos.acesso_backoffice", raise_exception=True)
def editar_processo_documentos_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Persiste anexos e documentos orçamentários do processo."""
    processo, _, redirecionamento, _ = _obter_contexto_edicao(request, pk)
    if redirecionamento:
        return redirecionamento

    documento_formset = DocumentoFormSet(request.POST, request.FILES, instance=processo, prefix="documento")
    next_url = request.POST.get("next") or ""

    if not documento_formset.is_valid():
        erros_validacao = _mensagens_validacao_formset_documentos(documento_formset)
        if erros_validacao:
            for erro in erros_validacao[:5]:
                messages.error(request, erro)
            if len(erros_validacao) > 5:
                messages.error(
                    request,
                    f"Existem mais {len(erros_validacao) - 5} erro(s) de validação nos documentos.",
                )
        else:
            messages.error(request, "Verifique os erros nos documentos.")

        logger.warning(
            "Validação do formset de documentos falhou para processo_id=%s erros=%s",
            pk,
            documento_formset.errors,
        )
        return redirect("editar_processo_documentos", pk=pk)

    try:
        _salvar_formsets_em_transacao(documento_formset)
        messages.success(request, f"Documentos do Processo #{pk} atualizados com sucesso!")
        return _redirect_seguro_ou_fallback(request, next_url, "editar_processo", pk)
    except (DatabaseError, TypeError, ValueError, OSError):
        logger.exception("Erro ao atualizar documentos do processo %s", pk)
        messages.error(request, "Erro interno ao salvar os documentos.")
        return redirect("editar_processo_documentos", pk=pk)


@require_POST
@permission_required("pagamentos.acesso_backoffice", raise_exception=True)
def extrair_codigo_barras_documento_action(request: HttpRequest, pk: int, documento_id: int) -> HttpResponse:
    """Extrai e persiste o código de barras de um documento já anexado ao processo."""
    processo, _, redirecionamento, _ = _obter_contexto_edicao(request, pk)
    if redirecionamento:
        return redirecionamento

    documento = get_object_or_404(DocumentoProcesso, id=documento_id, processo=processo)

    if not _documento_eh_boleto_bancario(documento):
        messages.warning(request, "Extração permitida apenas para documentos do tipo BOLETO BANCÁRIO.")
        return redirect("editar_processo_documentos", pk=pk)

    if not documento.arquivo:
        messages.error(request, "Documento sem arquivo para extração de código de barras.")
        return redirect("editar_processo_documentos", pk=pk)

    try:
        with documento.arquivo.open("rb") as arquivo_pdf:
            dados = processar_pdf_boleto(arquivo_pdf) or {}
        codigo_barras = (dados.get("codigo_barras") or "").strip()
        if not codigo_barras:
            messages.warning(request, "Não foi possível localizar linha digitável válida neste documento.")
            return redirect("editar_processo_documentos", pk=pk)

        with transaction.atomic():
            boleto = Boleto_Bancario.objects.filter(pk=documento.pk).first()
            if boleto is None:
                boleto = Boleto_Bancario(
                    pk=documento.pk,
                    documentoprocesso_ptr=documento,
                    processo=documento.processo,
                    tipo=documento.tipo,
                    ordem=documento.ordem,
                    arquivo=documento.arquivo,
                    imutavel=documento.imutavel,
                    codigo_barras=codigo_barras,
                )
                boleto.save(force_insert=True)
            else:
                boleto.codigo_barras = codigo_barras
                boleto.save(update_fields=["codigo_barras"])

        messages.success(request, "Código de barras extraído com sucesso.")
    except (PyPDF2.errors.PdfReadError, OSError, TypeError, ValueError):
        logger.exception(
            "Erro ao extrair código de barras do documento %s do processo %s",
            documento_id,
            pk,
        )
        messages.error(request, "Erro ao processar o PDF para extração do código de barras.")

    return redirect("editar_processo_documentos", pk=pk)


def _extrair_e_persistir_barcode(documento: DocumentoProcesso) -> bool:
    """Extrai e persiste código de barras de um único DocumentoProcesso do tipo boleto.

    Retorna True em caso de sucesso, False se não foi possível extrair ou salvar.
    Não propaga exceções — o chamador decide como contabilizar.
    """
    if not documento.arquivo:
        return False
    try:
        with documento.arquivo.open("rb") as arquivo_pdf:
            dados = processar_pdf_boleto(arquivo_pdf) or {}
        codigo_barras = (dados.get("codigo_barras") or "").strip()
        if not codigo_barras:
            return False
        with transaction.atomic():
            boleto = Boleto_Bancario.objects.filter(pk=documento.pk).first()
            if boleto is None:
                boleto = Boleto_Bancario(
                    pk=documento.pk,
                    documentoprocesso_ptr=documento,
                    processo=documento.processo,
                    tipo=documento.tipo,
                    ordem=documento.ordem,
                    arquivo=documento.arquivo,
                    imutavel=documento.imutavel,
                    codigo_barras=codigo_barras,
                )
                boleto.save(force_insert=True)
            else:
                boleto.codigo_barras = codigo_barras
                boleto.save(update_fields=["codigo_barras"])
        return True
    except (PyPDF2.errors.PdfReadError, OSError, TypeError, ValueError):
        logger.exception("Falha ao extrair código de barras do documento %s", documento.pk)
        return False


@require_POST
@permission_required("pagamentos.acesso_backoffice", raise_exception=True)
def extrair_codigos_barras_lote_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Extrai e persiste códigos de barras de todos os documentos BOLETO BANCÁRIO do processo."""
    processo, _, redirecionamento, _ = _obter_contexto_edicao(request, pk)
    if redirecionamento:
        return redirecionamento

    boletos = (
        processo.documentos.select_related("tipo")
        .filter(arquivo__isnull=False)
        .exclude(arquivo="")
    )
    boletos = [doc for doc in boletos if _documento_eh_boleto_bancario(doc)]

    total = len(boletos)
    if total == 0:
        messages.warning(request, "Nenhum documento do tipo BOLETO BANCÁRIO com arquivo encontrado neste processo.")
        return redirect("editar_processo_documentos", pk=pk)

    sucessos = sum(1 for doc in boletos if _extrair_e_persistir_barcode(doc))
    falhas = total - sucessos

    if falhas == 0:
        messages.success(
            request,
            f"{total} boleto(s) processado(s): {sucessos} extraído(s) com sucesso, {falhas} falha(s).",
        )
    elif sucessos == 0:
        messages.error(
            request,
            f"{total} boleto(s) processado(s): {sucessos} extraído(s) com sucesso, {falhas} falha(s).",
        )
    else:
        messages.warning(
            request,
            f"{total} boleto(s) processado(s): {sucessos} extraído(s) com sucesso, {falhas} falha(s).",
        )

    return redirect("editar_processo_documentos", pk=pk)


@require_POST
@permission_required("pagamentos.acesso_backoffice", raise_exception=True)
def editar_processo_pendencias_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Persiste pendências administrativas do processo."""
    processo, _, redirecionamento, somente_documentos = _obter_contexto_edicao(request, pk)
    if redirecionamento:
        return redirecionamento
    if somente_documentos:
        messages.error(request, "Neste status, apenas documentos podem ser alterados.")
        return redirect("editar_processo_documentos", pk=pk)

    row_action = (request.POST.get("pendencia_action") or "").strip().lower()
    pendencia_id = request.POST.get("pendencia_id")

    if row_action in PENDENCIA_ACAO_STATUS and not pendencia_id:
        messages.error(request, "Não foi possível identificar a pendência selecionada.")
        return redirect("editar_processo_pendencias", pk=pk)

    if row_action in PENDENCIA_ACAO_STATUS and pendencia_id:
        pendencia = get_object_or_400(Pendencia, id=pendencia_id, processo=processo)
        status_destino = PENDENCIA_ACAO_STATUS[row_action]

        try:
            _atualizar_status_pendencia(pendencia, status_destino)
            messages.success(request, f"Pendência #{pendencia.id} marcada como {status_destino}.")
        except (DatabaseError, TypeError, ValueError):
            logger.exception("Erro ao atualizar status da pendência %s do processo %s", pendencia_id, pk)
            messages.error(request, "Erro interno ao atualizar o status da pendência.")

        return redirect("editar_processo_pendencias", pk=pk)

    pendencia_formset = PendenciaFormSet(request.POST, instance=processo, prefix="pendencia")
    next_url = request.POST.get("next") or ""

    if not pendencia_formset.is_valid():
        messages.error(request, "Verifique os erros nas pendências.")
        return redirect("editar_processo_pendencias", pk=pk)

    try:
        _salvar_formsets_em_transacao(pendencia_formset)
        messages.success(request, f"Pendências do Processo #{pk} atualizadas com sucesso!")
        return _redirect_seguro_ou_fallback(request, next_url, "editar_processo", pk)
    except (DatabaseError, TypeError, ValueError):
        logger.exception("Erro ao atualizar pendências do processo %s", pk)
        messages.error(request, "Erro interno ao salvar as pendências.")
        return redirect("editar_processo_pendencias", pk=pk)


@permission_required("pagamentos.pode_operar_contas_pagar", raise_exception=True)
@require_POST
@transaction.atomic
def toggle_documento_fiscal_action(request, processo_pk, documento_pk):
    """Alterna o vínculo fiscal de um documento do processo."""
    processo = get_object_or_404(Processo, id=processo_pk)

    if _status_bloqueia_gestao_fiscal(processo):
        return JsonResponse(
            {
                "status": "blocked",
                "message": (
                    "Gestão fiscal bloqueada no pós-pagamento. "
                    "Use contingência para ajustes auditáveis."
                ),
            },
            status=409,
        )

    doc = get_object_or_404(Boleto_Bancario, id=documento_pk, processo=processo)

    ct = ContentType.objects.get_for_model(doc)
    nota = DocumentoFiscal.objects.filter(content_type=ct, object_id=doc.id).first()

    if nota is not None:
        nota.retencoes.all().delete()
        nota.delete()
        _sincronizar_totais_processo_fiscal(processo)
        logger.info(
            "mutation=remove_documento_fiscal processo_id=%s documento_pk=%s user_id=%s",
            processo.pk, documento_pk, request.user.pk
        )
        return JsonResponse({"status": "removed", "message": "Documento fiscal removido."})

    nota = DocumentoFiscal.objects.create(
        processo=processo,
        content_type=ct,
        object_id=doc.id,
        numero_nota_fiscal=f"DOC-{doc.ordem}",
        data_emissao=date.today(),
        valor_bruto=Decimal("0"),
        valor_liquido=Decimal("0"),
    )
    _sincronizar_totais_processo_fiscal(processo)
    logger.info(
        "mutation=create_documento_fiscal processo_id=%s documento_pk=%s user_id=%s nota_id=%s",
        processo.pk, documento_pk, request.user.pk, nota.pk
    )
    return JsonResponse(
        {
            "status": "created",
            "nota_id": nota.id,
            "message": "Documento marcado como fiscal.",
        }
    )


@permission_required("pagamentos.pode_operar_contas_pagar", raise_exception=True)
@require_POST
@transaction.atomic
def salvar_nota_fiscal_action(request, processo_pk, nota_pk):
    """Salva os dados da nota fiscal, retenções e pendência de ateste."""
    processo = get_object_or_404(Processo, id=processo_pk)

    if _status_bloqueia_gestao_fiscal(processo):
        return JsonResponse(
            {
                "status": "blocked",
                "message": "Gestão fiscal bloqueada no pós-pagamento. Use contingência para ajustes auditáveis.",
            },
            status=409,
        )

    nota = get_object_or_404(DocumentoFiscal, id=nota_pk, processo=processo)

    try:
        body = json.loads(request.body)
    except (ValueError, AttributeError):
        return JsonResponse({"status": "error", "error": "JSON inválido."}, status=400)

    erro = _atualizar_campos_nota(nota, body)
    if erro:
        return erro

    nota.save()

    erro = _salvar_retencoes(nota, body)
    if erro:
        return erro

    _sincronizar_totais_processo_fiscal(processo)
    _atualizar_pendencia_ateste(processo, nota)

    logger.info(
        "mutation=salvar_nota_fiscal processo_id=%s nota_id=%s user_id=%s",
        processo.pk, nota.pk, request.user.pk
    )
    return JsonResponse({"status": "ok", "message": "Nota fiscal salva com sucesso."})


def _salvar_retencoes(nota, body):
    """Altera retenções existentes em-place e cria/remove conforme o payload recebido."""
    codigos = body.get("imposto_codes", [])
    valores = body.get("imposto_values", [])
    rendimentos = body.get("imposto_rendimentos", [])
    beneficiarios = body.get("imposto_beneficiarios", [])

    # Parse all incoming rows first to catch validation errors early.
    incoming = []
    for codigo_id, rendimento, valor, beneficiario in zip(codigos, rendimentos, valores, beneficiarios):
        if not (codigo_id and valor):
            continue
        try:
            beneficiario_id = int(beneficiario) if beneficiario and str(beneficiario).strip() else None
            rendimento_valor = (
                Decimal(str(rendimento).replace(",", ".")) if rendimento and str(rendimento).strip() else None
            )
            imposto_valor = Decimal(str(valor).replace(",", "."))
        except (ValueError, TypeError, InvalidOperation):
            return JsonResponse(
                {
                    "status": "error",
                    "error": f"Erro ao processar o imposto {codigo_id}: Verifique se os valores numéricos são válidos.",
                },
                status=400,
            )
        incoming.append((codigo_id, rendimento_valor, imposto_valor, beneficiario_id))

    existing = list(nota.retencoes.all().order_by("id"))

    # Resolve the "A RETER" status once, only if new records will be created.
    status_a_reter = None
    if len(incoming) > len(existing):
        status_a_reter, _ = StatusChoicesRetencoes.objects.get_or_create(
            status_choice__iexact="A RETER",
            defaults={"status_choice": "A RETER"},
        )

    # Update in-place — preserves IDs and HistoricalRecords.
    for ret, (codigo_id, rendimento_valor, imposto_valor, beneficiario_id) in zip(existing, incoming):
        ret.codigo_id = codigo_id
        ret.rendimento_tributavel = rendimento_valor
        ret.valor = imposto_valor
        ret.beneficiario_id = beneficiario_id
        ret.save(update_fields=["codigo_id", "rendimento_tributavel", "valor", "beneficiario_id"])

    # Create new rows beyond the existing count.
    for codigo_id, rendimento_valor, imposto_valor, beneficiario_id in incoming[len(existing):]:
        RetencaoImposto.objects.create(
            nota_fiscal=nota,
            codigo_id=codigo_id,
            rendimento_tributavel=rendimento_valor,
            valor=imposto_valor,
            beneficiario_id=beneficiario_id,
            status=status_a_reter,
        )

    # Delete rows that were removed on the frontend.
    for ret in existing[len(incoming):]:
        ret.delete()

    total_retencoes = nota.retencoes.aggregate(total=Sum("valor"))["total"] or 0
    nota.valor_liquido = (nota.valor_bruto or 0) - total_retencoes
    nota.save(update_fields=["valor_liquido"])

    return None


def _sincronizar_totais_processo_fiscal(processo):
    """Sincroniza valores do processo com base nas notas fiscais e retenções associadas."""
    total_bruto = processo.notas_fiscais.aggregate(total=Sum("valor_bruto"))["total"] or Decimal("0")
    total_retencoes = RetencaoImposto.objects.filter(nota_fiscal__processo=processo).aggregate(total=Sum("valor"))["total"] or Decimal("0")
    processo.valor_bruto = total_bruto
    processo.valor_liquido = total_bruto - total_retencoes
    processo.save(update_fields=["valor_bruto", "valor_liquido"])


def _atualizar_pendencia_ateste(processo, nota):
    """Cria ou remove a pendência de ateste de liquidação conforme o estado da nota."""
    tipo_pendencia, _ = TiposDePendencias.objects.get_or_create(
        tipo_pendencia__iexact="ATESTE DE LIQUIDAÇÃO",
        defaults={"tipo_pendencia": "ATESTE DE LIQUIDAÇÃO"},
    )

    if not nota.atestada:
        status_pendencia, _ = StatusChoicesPendencias.objects.get_or_create(
            opcao_status__iexact="A RESOLVER",
            defaults={"opcao_status": "A RESOLVER"},
        )
        if not processo.pendencias.filter(tipo=tipo_pendencia).exists():
            Pendencia.objects.create(
                processo=processo,
                tipo=tipo_pendencia,
                descricao="DOCUMENTO PENDENTE DE ATESTE DE FISCAL DE CONTRATO",
                status=status_pendencia,
            )
    else:
        outras_nao_atestadas = processo.notas_fiscais.filter(atestada=False).exclude(id=nota.id).exists()
        if not outras_nao_atestadas:
            processo.pendencias.filter(tipo=tipo_pendencia).delete()


__all__ = [
    "add_process_action",
    "editar_processo_capa_action",
    "editar_processo_documentos_action",
    "editar_processo_pendencias_action",
    "_status_bloqueia_gestao_fiscal",
    "_status_bloqueia_exclusao_nota_fiscal",
]
