"""Ação de cancelamento de processo (POST)."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from pagamentos.domain_models import Processo
from pagamentos.services.cancelamentos import (
    extrair_dados_devolucao_do_post,
    registrar_cancelamento_processo,
)

logger = logging.getLogger(__name__)


@require_POST
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def cancelar_processo_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Cancela processo com justificativa obrigatória e devolução quando pago."""
    justificativa = (request.POST.get("justificativa") or "").strip()
    if not justificativa:
        messages.error(request, "A justificativa do cancelamento é obrigatória.")
        return redirect("cancelar_processo_spoke", pk=pk)

    processo = get_object_or_404(Processo.objects.select_related("status"), id=pk)

    try:
        registrar_cancelamento_processo(
            processo,
            justificativa,
            request.user,
            dados_devolucao=extrair_dados_devolucao_do_post(request),
        )
    except ValidationError as exc:
        for msg in exc.messages:
            messages.error(request, msg)
        return redirect("cancelar_processo_spoke", pk=pk)

    logger.info("mutation=cancelar_processo processo_id=%s user_id=%s", processo.id, request.user.pk)
    messages.warning(request, f"Processo #{processo.id} cancelado.")
    return redirect("process_detail", pk=processo.id)


__all__ = ["cancelar_processo_action"]
