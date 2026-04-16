"""Endpoints API da etapa de cadastro pré-pagamento."""

import json
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import PyPDF2
from django.contrib.auth.decorators import permission_required
from django.db import DatabaseError
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.views.decorators.http import require_POST

from .helpers import processar_pdf_boleto

logger = logging.getLogger(__name__)

from credores.models import Credor
from fiscal.models import DocumentoFiscal, RetencaoImposto
from fluxo.domain_models import Boleto_Bancario, Pendencia, Processo, StatusChoicesPendencias, TiposDeDocumento, TiposDePendencias
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from .actions import _status_bloqueia_gestao_fiscal


@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
def api_tipos_documento_por_pagamento(request):
    """Lista tipos de documento ativos vinculados a um tipo de pagamento."""
    tipo_pagamento_id = request.GET.get("tipo_pagamento_id")

    if not tipo_pagamento_id:
        return JsonResponse({"sucesso": False, "erro": "ID não fornecido"})

    try:
        documentos_validos = (
            TiposDeDocumento.objects.filter(tipo_de_pagamento_id=tipo_pagamento_id, is_active=True)
            .values("id", "tipo_de_documento")
            .order_by("tipo_de_documento")
        )

        lista_docs = list(documentos_validos)
        return JsonResponse({"sucesso": True, "tipos": lista_docs})
    except (DatabaseError, TypeError, ValueError) as e:
        return JsonResponse({"sucesso": False, "erro": str(e)})


def _atualizar_campos_nota(nota, body):
    """Hidrata os campos escalares da nota a partir do body parsed."""
    emitente_id = body.get("nome_emitente")
    if emitente_id:
        try:
            nota.nome_emitente = Credor.objects.get(id=int(emitente_id))
        except (Credor.DoesNotExist, ValueError, TypeError):
            nota.nome_emitente = None
    else:
        nota.nome_emitente = None

    numero = body.get("numero_nota_fiscal")
    if numero:
        nota.numero_nota_fiscal = numero

    data_str = body.get("data_emissao", "")
    if data_str:
        try:
            nota.data_emissao = datetime.strptime(str(data_str), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return JsonResponse(
                {"status": "error", "error": "Data de emissão inválida. Use o formato AAAA-MM-DD."},
                status=400,
            )

    valor_bruto = body.get("valor_bruto", "")
    if valor_bruto:
        try:
            nota.valor_bruto = Decimal(str(valor_bruto).replace(",", "."))
        except (InvalidOperation, ValueError, TypeError):
            return JsonResponse(
                {"status": "error", "error": "Valor bruto inválido. Informe um valor numérico válido."},
                status=400,
            )

    fiscal_id = body.get("fiscal_contrato")
    if fiscal_id:
        try:
            nota.fiscal_contrato = User.objects.get(id=int(fiscal_id))
        except (User.DoesNotExist, ValueError, TypeError):
            nota.fiscal_contrato = None
    else:
        nota.fiscal_contrato = None

    atestada = body.get("atestada")
    nota.atestada = bool(atestada) if isinstance(atestada, bool) else str(atestada).lower() in ("true", "1", "on")

    serie = body.get("serie_nota_fiscal", "")
    nota.serie_nota_fiscal = serie.strip() if serie else None

    codigo_servico = body.get("codigo_servico_inss", "")
    nota.codigo_servico_inss = codigo_servico.strip() if codigo_servico else None

    return None


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
                float(str(rendimento).replace(",", ".")) if rendimento and str(rendimento).strip() else None
            )
            imposto_valor = float(str(valor).replace(",", "."))
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


@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
@require_POST
def api_toggle_documento_fiscal(request, processo_pk, documento_pk):
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
        return JsonResponse({"status": "removed", "message": "Documento fiscal removido."})

    nota = DocumentoFiscal.objects.create(
        processo=processo,
        content_type=ct,
        object_id=doc.id,
        numero_nota_fiscal=f"DOC-{doc.ordem}",
        data_emissao=date.today(),
        valor_bruto=0,
        valor_liquido=0,
    )
    _sincronizar_totais_processo_fiscal(processo)
    return JsonResponse(
        {
            "status": "created",
            "nota_id": nota.id,
            "message": "Documento marcado como fiscal.",
        }
    )


@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
@require_POST
@transaction.atomic
def api_salvar_nota_fiscal(request, processo_pk, nota_pk):
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
        body = request.POST

    erro = _atualizar_campos_nota(nota, body)
    if erro:
        return erro

    nota.save()

    erro = _salvar_retencoes(nota, body)
    if erro:
        return erro

    _sincronizar_totais_processo_fiscal(processo)
    _atualizar_pendencia_ateste(processo, nota)

    return JsonResponse({"status": "ok", "message": "Nota fiscal salva com sucesso."})


@permission_required("fluxo.pode_editar_processos", raise_exception=True)
def api_extrair_codigos_barras_upload(request):
    """Extrai dados de boleto a partir de upload único ou em lote de PDFs.

    Endpoint de cadastro: usado durante o upload de documentos de boleto para
    pré-preencher o campo código de barras antes de salvar o documento.
    """
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "erro": "Método não permitido."}, status=405)

    files = request.FILES.getlist("boleto_files")
    if not files:
        single_file = (
            request.FILES.get("boleto_file")
            or request.FILES.get("boleto_pdf")
            or request.FILES.get("file")
        )
        if single_file:
            files = [single_file]

    if not files:
        return JsonResponse({"sucesso": False, "erro": "Nenhum arquivo enviado."}, status=400)

    if len(files) == 1:
        try:
            dados = processar_pdf_boleto(files[0]) or {}
        except (PyPDF2.errors.PdfReadError, OSError, TypeError, ValueError):
            logger.exception(
                "Erro ao processar boleto no upload %s", getattr(files[0], "name", "")
            )
            return JsonResponse(
                {
                    "sucesso": False,
                    "erro": "Erro ao processar boleto. Verifique se o arquivo é um PDF válido.",
                },
                status=500,
            )
        return JsonResponse({"sucesso": True, "dados": dados})

    barcodes = []
    n_extraidos = 0
    n_falhas = 0

    for pdf_file in files:
        try:
            dados = processar_pdf_boleto(pdf_file)
            codigo = dados.get("codigo_barras", "") if dados else ""
            if codigo:
                barcodes.append(codigo)
                n_extraidos += 1
            else:
                barcodes.append(None)
                n_falhas += 1
        except (PyPDF2.errors.PdfReadError, OSError, TypeError, ValueError):
            logger.exception(
                "Erro ao extrair código de barras de '%s'", getattr(pdf_file, "name", "arquivo")
            )
            barcodes.append(None)
            n_falhas += 1

    return JsonResponse(
        {
            "sucesso": True,
            "n_extraidos": n_extraidos,
            "n_falhas": n_falhas,
            "barcodes": [b for b in barcodes if b],
        }
    )


__all__ = [
    "api_tipos_documento_por_pagamento",
    "api_toggle_documento_fiscal",
    "api_salvar_nota_fiscal",
    "api_extrair_codigos_barras_upload",
]
