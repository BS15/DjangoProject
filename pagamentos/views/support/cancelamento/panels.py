"""Spoke de cancelamento de processo (GET)."""

from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from pagamentos.domain_models import Processo, STATUS_PROCESSO_PAGOS_E_POSTERIORES


@require_GET
@permission_required("pagamentos.acesso_backoffice", raise_exception=True)
def cancelar_processo_spoke_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Exibe formulário de cancelamento de processo com campos de devolução quando pago."""
    processo = get_object_or_404(Processo.objects.select_related("status", "credor"), id=pk)
    processo_pago = bool(
        processo.status
        and (processo.status.opcao_status or "").upper() in STATUS_PROCESSO_PAGOS_E_POSTERIORES
    )
    return render(request, "pagamentos/cancelar_processo_spoke.html", {
        "processo": processo,
        "processo_pago": processo_pago,
    })


__all__ = ["cancelar_processo_spoke_view"]
