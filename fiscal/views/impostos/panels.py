"""Panel views for tax retention management."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render

from credores.models import Credor
from fiscal.models import DocumentoFiscal, RetencaoImposto
from fluxo.domain_models import Processo, StatusChoicesProcesso, TiposDePagamento
from fiscal.filters import RetencaoIndividualFilter, RetencaoNotaFilter, RetencaoProcessoFilter
from fluxo.utils import normalize_choice
from fluxo.views.helpers import _aplicar_filtro_por_opcao
from fluxo.views.shared import apply_filterset


@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def painel_impostos(request):
    """Panel for viewing and filtering tax retentions grouped by processos, notas, or individual items."""
    visao = request.GET.get("visao", "processos")
    status_agrupamento = normalize_choice(
        request.GET.get("status_agrupamento", "pendentes"),
        {"pendentes", "agrupados", "todos"},
        default="pendentes",
    )

    if visao == "processos":
        queryset_base = Processo.objects.filter(notas_fiscais__retencoes__isnull=False).distinct()
        queryset_base = _aplicar_filtro_por_opcao(
            queryset_base,
            status_agrupamento,
            {
                "pendentes": {"notas_fiscais__retencoes__processo_pagamento__isnull": True},
                "agrupados": {"notas_fiscais__retencoes__processo_pagamento__isnull": False},
            },
        )
        meu_filtro = apply_filterset(request, RetencaoProcessoFilter, queryset_base)
        itens = meu_filtro.qs.prefetch_related("notas_fiscais__retencoes__codigo", "notas_fiscais__retencoes__status")
    elif visao == "notas":
        queryset_base = DocumentoFiscal.objects.filter(retencoes__isnull=False).distinct()
        queryset_base = _aplicar_filtro_por_opcao(
            queryset_base,
            status_agrupamento,
            {
                "pendentes": {"retencoes__processo_pagamento__isnull": True},
                "agrupados": {"retencoes__processo_pagamento__isnull": False},
            },
        )
        meu_filtro = apply_filterset(request, RetencaoNotaFilter, queryset_base)
        itens = meu_filtro.qs.prefetch_related("retencoes__codigo", "retencoes__status", "processo")
    else:
        queryset_base = RetencaoImposto.objects.all().order_by("-id")
        queryset_base = _aplicar_filtro_por_opcao(
            queryset_base,
            status_agrupamento,
            {
                "pendentes": {"processo_pagamento__isnull": True},
                "agrupados": {"processo_pagamento__isnull": False},
            },
        )
        meu_filtro = apply_filterset(request, RetencaoIndividualFilter, queryset_base)
        itens = meu_filtro.qs.select_related("codigo", "status", "nota_fiscal", "nota_fiscal__processo")

    context = {
        "visao": visao,
        "status_agrupamento": status_agrupamento,
        "meu_filtro": meu_filtro,
        "itens": itens,
    }
    return render(request, "fiscal/painel_impostos.html", context)
