"""Panel views for tax retention management."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render

from fiscal.filters import RetencaoIndividualFilter
from fiscal.models import DocumentoPagamentoImposto, RetencaoImposto
from pagamentos.views.shared import apply_filterset


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

    context = {
        "filter": filtro,
        "retencoes": retencoes,
    }
    return render(request, "fiscal/painel_impostos.html", context)
