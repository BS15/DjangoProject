"""Panel views for tax retention management."""

from django.contrib.auth.decorators import permission_required
from django.contrib import messages
from django.db.models import Count, Sum
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from fiscal.filters import RetencaoIndividualFilter, RetencaoNotaFilter, RetencaoProcessoFilter
from fiscal.models import DocumentoFiscal, DocumentoPagamentoImposto, RetencaoImposto
from pagamentos.domain_models import Processo
from pagamentos.views.shared import apply_filterset

DEFAULT_VIEW = "individual"
VALID_VIEWS = {"individual", "nf", "processo"}


def _resolve_fonte_retentora_nome(retencao: RetencaoImposto) -> str:
    beneficiario = getattr(retencao, "beneficiario", None)
    if beneficiario and beneficiario.nome:
        return beneficiario.nome

    nota_fiscal = getattr(retencao, "nota_fiscal", None)
    emitente = getattr(nota_fiscal, "nome_emitente", None) if nota_fiscal else None
    if emitente and emitente.nome:
        return emitente.nome

    return "NOME NAO INFORMADO"


@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def painel_impostos_view(request):
    """Hub de gestão fiscal com retenções individuais filtráveis."""
    visao = (request.GET.get("visao") or DEFAULT_VIEW).strip().lower()
    if visao not in VALID_VIEWS:
        visao = DEFAULT_VIEW

    context = {"visao": visao}
    if visao == "nf":
        queryset_base = DocumentoFiscal.objects.select_related(
            "processo",
            "nome_emitente",
        )
        filtro = apply_filterset(request, RetencaoNotaFilter, queryset_base.order_by("-id"))
        notas = list(
            filtro.qs.distinct().annotate(
                total_retido=Sum("retencoes__valor"),
                qtd_retencoes=Count("retencoes", distinct=True),
            )
        )
        context.update({"filter": filtro, "notas_fiscais": notas})
    elif visao == "processo":
        queryset_base = Processo.objects.select_related("credor")
        filtro = apply_filterset(request, RetencaoProcessoFilter, queryset_base.order_by("-id"))
        processos = list(
            filtro.qs.distinct().annotate(
                total_retido=Sum("notas_fiscais__retencoes__valor"),
                qtd_retencoes=Count("notas_fiscais__retencoes", distinct=True),
                qtd_notas=Count("notas_fiscais", distinct=True),
            )
        )
        context.update({"filter": filtro, "processos": processos})
    else:
        queryset_base = RetencaoImposto.objects.select_related(
            "codigo",
            "status",
            "nota_fiscal",
            "nota_fiscal__nome_emitente",
            "beneficiario",
        ).order_by("-id")
        filtro = apply_filterset(request, RetencaoIndividualFilter, queryset_base)
        retencoes = list(filtro.qs.prefetch_related("documentos_pagamento"))
        retencao_ids = [r.id for r in retencoes]
        docs_completos = set(
            DocumentoPagamentoImposto.objects.filter(
                retencao_id__in=retencao_ids,
                relatorio_retencoes__isnull=False,
                guia_recolhimento__isnull=False,
                comprovante_pagamento__isnull=False,
            )
            .exclude(relatorio_retencoes="")
            .exclude(guia_recolhimento="")
            .exclude(comprovante_pagamento="")
            .values_list("retencao_id", flat=True)
        )
        for retencao in retencoes:
            retencao.fonte_retentora_nome = _resolve_fonte_retentora_nome(retencao)
            retencao.documentacao_completa = retencao.id in docs_completos
        context.update({"filter": filtro, "retencoes": retencoes})
    return render(request, "fiscal/painel_impostos.html", context)


@require_GET
@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def registrar_documentos_pagamento_view(request):
    """Spoke de registro de documentos para retenções passadas via query param ?ids=1,2,3."""
    ids_raw = request.GET.get("ids", "")
    retencao_ids = [int(x) for x in ids_raw.split(",") if x.strip().isdigit()]

    if not retencao_ids:
        messages.warning(request, "Nenhuma retenção foi selecionada para registro de documentos.")
        return redirect("painel_impostos_view")

    retencoes = list(
        RetencaoImposto.objects.select_related(
            "codigo",
            "status",
            "nota_fiscal",
            "nota_fiscal__nome_emitente",
            "beneficiario",
        )
        .filter(id__in=retencao_ids)
        .order_by("-id")
    )
    if not retencoes:
        messages.warning(request, "As retenções selecionadas não estão mais disponíveis.")
        return redirect("painel_impostos_view")

    for retencao in retencoes:
        retencao.fonte_retentora_nome = _resolve_fonte_retentora_nome(retencao)

    total_retido = sum((retencao.valor or 0) for retencao in retencoes)
    context = {
        "retencoes": retencoes,
        "retencao_ids": [r.id for r in retencoes],
        "qtd_retencoes": len(retencoes),
        "total_retido": total_retido,
    }
    return render(request, "fiscal/registrar_documentos_pagamento_retencoes.html", context)
