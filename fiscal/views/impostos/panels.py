"""Panel views for tax retention management."""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db.models import Count, Sum
from django.shortcuts import redirect, render

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


@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def revisar_agrupamento_retencoes_view(request):
    """Exibe a página de revisão antes de confirmar o agrupamento de retenções."""
    ids_raw = (request.GET.get("ids") or "").strip()
    if not ids_raw:
        messages.warning(request, "Nenhum item selecionado para revisão.")
        return redirect("painel_impostos_view")

    try:
        ids = [int(i) for i in ids_raw.split(",") if i.strip().isdigit()]
    except ValueError:
        messages.warning(request, "Parâmetros de seleção inválidos.")
        return redirect("painel_impostos_view")

    if not ids:
        messages.warning(request, "Nenhum item selecionado para revisão.")
        return redirect("painel_impostos_view")

    retencoes = list(
        RetencaoImposto.objects.select_related(
            "codigo",
            "status",
            "nota_fiscal",
            "nota_fiscal__nome_emitente",
            "beneficiario",
        )
        .filter(id__in=ids, processo_pagamento__isnull=True)
        .order_by("competencia", "id")
    )

    for retencao in retencoes:
        retencao.fonte_retentora_nome = _resolve_fonte_retentora_nome(retencao)

    total_valor = sum((r.valor or Decimal("0")) for r in retencoes)
    total_base = sum((r.rendimento_tributavel or Decimal("0")) for r in retencoes)
    qtd = len(retencoes)

    ids_inacessiveis = len(ids) - qtd
    if ids_inacessiveis:
        messages.warning(
            request,
            f"{ids_inacessiveis} retenção(ões) ignorada(s) por já estarem agrupadas ou não existirem.",
        )

    if not retencoes:
        messages.warning(request, "Nenhuma retenção elegível encontrada para agrupamento.")
        return redirect("painel_impostos_view")

    return render(
        request,
        "fiscal/revisar_agrupamento_retencoes.html",
        {
            "retencoes": retencoes,
            "total_valor": total_valor,
            "total_base": total_base,
            "qtd": qtd,
        },
    )

