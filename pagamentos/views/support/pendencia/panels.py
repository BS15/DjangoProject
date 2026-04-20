"""Paineis de pendencias (GET views)."""

from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET

from pagamentos.filters import PendenciaFilter
from pagamentos.domain_models import Pendencia
from pagamentos.views.shared import render_filtered_list


@require_GET
@permission_required("pagamentos.acesso_backoffice", raise_exception=True)
def painel_pendencias_view(request: HttpRequest) -> HttpResponse:
    """Painel de pendências vinculadas a processos."""
    queryset_base = Pendencia.objects.select_related(
        "processo", "status", "tipo", "processo__credor", "processo__status"
    ).all().order_by("-id")
    return render_filtered_list(
        request,
        queryset=queryset_base,
        filter_class=PendenciaFilter,
        template_name="pagamentos/painel_pendencias.html",
        items_key="pendencias",
        extra_context={
            "pode_interagir": request.user.has_perm("pagamentos.acesso_backoffice"),
        },
    )


__all__ = ["painel_pendencias_view"]
