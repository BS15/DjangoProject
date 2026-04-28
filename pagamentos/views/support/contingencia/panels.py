"""Paineis de contingencia (GET views)."""

from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from pagamentos.filters import ContingenciaFilter
from pagamentos.domain_models import Contingencia
from pagamentos.views.shared import render_filtered_list


@require_GET
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def painel_contingencias_view(request: HttpRequest) -> HttpResponse:
    """Lista todas as contingencias com filtros e ordenacao."""
    queryset = Contingencia.objects.select_related(
        "processo",
        "solicitante",
        "aprovado_por_supervisor",
        "aprovado_por_ordenador",
        "aprovado_por_conselho",
        "revisado_por_contadora",
    ).order_by("-data_solicitacao")
    return render_filtered_list(
        request,
        queryset=queryset,
        filter_class=ContingenciaFilter,
        template_name="pagamentos/painel_contingencias.html",
        items_key="contingencias",
        filter_key="filter",
        sort_fields={
            "id": "id",
            "processo": "processo__id",
            "solicitante": "solicitante__username",
            "data_solicitacao": "data_solicitacao",
            "justificativa": "justificativa",
            "status": "status",
        },
        default_ordem="data_solicitacao",
        default_direcao="desc",
        tie_breaker="-id",
    )


@require_GET
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def add_contingencia_view(request: HttpRequest) -> HttpResponse:
    """Renderiza o formulario para abertura de contingencia."""
    return render(request, "pagamentos/add_contingencia.html")


__all__ = [
    "painel_contingencias_view",
    "add_contingencia_view",
]
