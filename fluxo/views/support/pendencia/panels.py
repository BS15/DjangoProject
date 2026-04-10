"""Paineis de pendencias (GET views)."""

from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET

from fluxo.filters import PendenciaFilter
from fluxo.models import Pendencia
from fluxo.views.shared import render_filtered_list


@require_GET
@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def painel_pendencias_view(request: HttpRequest) -> HttpResponse:
    """Painel de pendências vinculadas a processos."""
    queryset_base = Pendencia.objects.select_related(
        "processo", "status", "tipo", "processo__credor", "processo__status"
    ).all().order_by("-id")
    return render_filtered_list(
        request,
        queryset=queryset_base,
        filter_class=PendenciaFilter,
        template_name="fluxo/painel_pendencias.html",
        items_key="pendencias",
    )


__all__ = ["painel_pendencias_view"]
