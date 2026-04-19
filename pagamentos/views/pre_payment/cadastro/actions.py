"""Acoes POST da etapa de documentos fiscais do cadastro."""

import logging
from typing import Optional

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
from fiscal.models import DocumentoFiscal, RetencaoImposto
from pagamentos.domain_models import (
    Boleto_Bancario,
    TiposDePendencias,
    StatusChoicesPendencias,
    Pendencia,
    Processo,
)
from .forms import DocumentoFormSet, DocumentoOrcamentarioFormSet, PendenciaFormSet, ProcessoForm
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

    status_atual = (processo.status.status_choice or "").upper()
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
        status_choice__iexact=status_destino,
        defaults={"status_choice": status_destino},
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

    processo_form = ProcessoForm(request.POST, instance=processo, prefix="processo")
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
        messages.error(request, "Verifique os erros nos documentos.")
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
    """Recria as retenções de impostos da nota e recalcula o valor líquido."""
    nota.retencoes.all().delete()
    codigos = body.get("imposto_codes", [])
    valores = body.get("imposto_values", [])
    rendimentos = body.get("imposto_rendimentos", [])
    beneficiarios = body.get("imposto_beneficiarios", [])

    for codigo_id, rendimento, valor, beneficiario in zip(codigos, rendimentos, valores, beneficiarios):
        if not (codigo_id and valor):
            continue
        try:
            beneficiario_id = int(beneficiario) if beneficiario and str(beneficiario).strip() else None
        except (ValueError, TypeError):
            beneficiario_id = None
        try:
            rendimento_valor = (
                Decimal(str(rendimento).replace(",", ".")) if rendimento and str(rendimento).strip() else None
            )
            imposto_valor = Decimal(str(valor).replace(",", "."))
            RetencaoImposto.objects.create(
                nota_fiscal=nota,
                codigo_id=codigo_id,
                rendimento_tributavel=rendimento_valor,
                valor=imposto_valor,
                beneficiario_id=beneficiario_id,
            )
        except (ValueError, TypeError, InvalidOperation):
            return JsonResponse(
                {
                    "status": "error",
                    "error": f"Erro ao processar o imposto {codigo_id}: Verifique se os valores numéricos são válidos.",
                },
                status=400,
            )

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
        tipo_de_pendencia__iexact="ATESTE DE LIQUIDAÇÃO",
        defaults={"tipo_de_pendencia": "ATESTE DE LIQUIDAÇÃO"},
    )

    if not nota.atestada:
        status_pendencia, _ = StatusChoicesPendencias.objects.get_or_create(
            status_choice__iexact="A RESOLVER",
            defaults={"status_choice": "A RESOLVER"},
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
