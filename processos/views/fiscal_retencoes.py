"""Views relacionadas a retencoes e agrupamento de impostos."""

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render

from ..filters import RetencaoIndividualFilter, RetencaoNotaFilter, RetencaoProcessoFilter
from ..models import Credor, DocumentoFiscal, Processo, RetencaoImposto, StatusChoicesProcesso, TiposDePagamento
from .helpers import _aplicar_filtro_por_opcao, _normalizar_filtro_opcao


def painel_impostos(request):
    visao = request.GET.get("visao", "processos")
    status_agrupamento = _normalizar_filtro_opcao(
        request.GET.get("status_agrupamento", "pendentes"),
        {"pendentes", "agrupados"},
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
        meu_filtro = RetencaoProcessoFilter(request.GET, queryset=queryset_base)
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
        meu_filtro = RetencaoNotaFilter(request.GET, queryset=queryset_base)
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
        meu_filtro = RetencaoIndividualFilter(request.GET, queryset=queryset_base)
        itens = meu_filtro.qs.select_related("codigo", "status", "nota_fiscal", "nota_fiscal__processo")

    context = {
        "visao": visao,
        "status_agrupamento": status_agrupamento,
        "meu_filtro": meu_filtro,
        "itens": itens,
    }
    return render(request, "fiscal/painel_impostos.html", context)


def agrupar_impostos_view(request):
    if request.method != "POST":
        return redirect("painel_impostos")

    selecionados = request.POST.getlist("itens_selecionados")
    visao = request.POST.get("visao_atual")

    if not selecionados:
        messages.warning(request, "Nenhum item selecionado para agrupar.")
        return redirect("painel_impostos")

    total_impostos = 0

    if visao == "processos":
        retencoes = RetencaoImposto.objects.filter(nota_fiscal__processo__id__in=selecionados)
    elif visao == "notas":
        retencoes = RetencaoImposto.objects.filter(nota_fiscal__id__in=selecionados)
    else:
        retencoes = RetencaoImposto.objects.filter(id__in=selecionados)

    for retencao in retencoes:
        if retencao.valor:
            total_impostos += retencao.valor

    if total_impostos <= 0:
        messages.warning(request, "Os itens selecionados não possuem valores válidos.")
        return redirect("painel_impostos")

    status_padrao, _ = StatusChoicesProcesso.objects.get_or_create(
        status_choice__iexact="A PAGAR - PENDENTE AUTORIZAÇÃO",
        defaults={"status_choice": "A PAGAR - PENDENTE AUTORIZAÇÃO"},
    )

    credor_orgao, _ = Credor.objects.get_or_create(
        nome="Órgão Arrecadador (A Definir)",
        defaults={"nome": "Órgão Arrecadador (A Definir)"},
    )

    tipo_pagamento_impostos, _ = TiposDePagamento.objects.get_or_create(
        tipo_de_pagamento="IMPOSTOS"
    )

    novo_processo = Processo.objects.create(
        credor=credor_orgao,
        valor_bruto=total_impostos,
        valor_liquido=total_impostos,
        detalhamento="Pagamento Agrupado de Impostos Retidos",
        observacao="Gerado automaticamente.",
        status=status_padrao,
        tipo_pagamento=tipo_pagamento_impostos,
    )

    retencoes.update(processo_pagamento=novo_processo)

    messages.success(request, f"Processo #{novo_processo.id} para recolhimento gerado com sucesso!")
    return redirect("editar_processo", pk=novo_processo.id)


def api_processar_retencoes(request):
    """
    Recebe um arquivo PDF de Nota Fiscal e aplica as regras de negócio de
    retenções, retornando o JSON padronizado da Etapa 6.
    """
    if request.method != "POST" or not request.FILES.get("arquivo"):
        return JsonResponse(
            {"status": "error", "message": "Requisição inválida ou arquivo ausente"},
            status=400,
        )

    return JsonResponse(
        {"status": "error", "message": "Extração por IA não disponível."},
        status=400,
    )
