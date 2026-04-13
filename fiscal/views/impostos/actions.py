"""Action views for tax retention grouping and API operations."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from credores.models import Credor
from fiscal.models import RetencaoImposto
from fluxo.domain_models import Processo, StatusChoicesProcesso, TiposDePagamento


@require_POST
@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def agrupar_retencoes_action(request):
    """Agrupa retenções selecionadas em um novo processo de recolhimento."""
    selecionados = request.POST.getlist("retencao_ids") or request.POST.getlist("itens_selecionados")

    if not selecionados:
        messages.warning(request, "Nenhum item selecionado para agrupar.")
        return redirect("painel_impostos_view")

    total_impostos = 0

    retencoes = RetencaoImposto.objects.filter(id__in=selecionados)

    for retencao in retencoes:
        if retencao.valor:
            total_impostos += retencao.valor

    if total_impostos <= 0:
        messages.warning(request, "Os itens selecionados não possuem valores válidos.")
        return redirect("painel_impostos_view")

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


@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def agrupar_impostos_view(request):
    """Alias legado do agrupamento de retenções."""
    if request.method != "POST":
        return redirect("painel_impostos_view")
    return agrupar_retencoes_action(request)


@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def api_processar_retencoes(request):
    """
    Process a PDF invoice file and apply tax retention business rules,
    returning standardized JSON.
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
