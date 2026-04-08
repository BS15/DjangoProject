"""Paineis de contingencia (GET views)."""

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET

from .....filters import ContingenciaFilter
from .....models import Contingencia
from ....shared import apply_filterset, render_filtered_list
from .helpers import _usuario_pode_acessar_painel_contingencias


@require_GET
def painel_contingencias_view(request: HttpRequest) -> HttpResponse:
    """Lista todas as contingencias com filtros e ordenacao."""
    if not _usuario_pode_acessar_painel_contingencias(request.user):
        raise PermissionDenied

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
        template_name="fluxo/painel_contingencias.html",
        items_key="contingencias",
        filter_key="filter",
    )


@require_GET
def add_contingencia_view(request: HttpRequest) -> HttpResponse:
    """Renderiza o formulario para abertura de contingencia."""
    from django.contrib.auth.decorators import permission_required
    from django.shortcuts import render

    @permission_required("processos.acesso_backoffice", raise_exception=True)
    def _view(request: HttpRequest) -> HttpResponse:
        return render(request, "fluxo/add_contingencia.html")

    return _view(request)


__all__ = [
    "painel_contingencias_view",
    "add_contingencia_view",
]
