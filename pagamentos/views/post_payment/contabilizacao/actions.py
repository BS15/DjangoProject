"""Acoes POST da etapa de contabilizacao."""

from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_POST

from fluxo.domain_models import ProcessoStatus
from fluxo.views.helpers import _aprovar_processo_view, _iniciar_fila_sessao, _recusar_processo_view


@require_POST
@permission_required("fluxo.pode_contabilizar", raise_exception=True)
def iniciar_contabilizacao_action(request: HttpRequest) -> HttpResponse:
    """Inicializa a fila de trabalho da contabilizacao na sessao."""
    return _iniciar_fila_sessao(
        request,
        "contabilizacao_queue",
        "painel_contabilizacao",
        "contabilizacao_processo",
    )


@require_POST
@permission_required("fluxo.pode_contabilizar", raise_exception=True)
def aprovar_contabilizacao_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Aprova contabilizacao por rota direta e avanca status do processo."""
    return _aprovar_processo_view(
        request,
        pk,
        permission="fluxo.pode_contabilizar",
        new_status=ProcessoStatus.CONTABILIZADO_CONSELHO,
        success_message="Processo #{processo_id} contabilizado e enviado ao Conselho Fiscal!",
        redirect_to="painel_contabilizacao",
    )


@require_POST
@permission_required("fluxo.pode_contabilizar", raise_exception=True)
def recusar_contabilizacao_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Recusa contabilizacao e devolve o processo para conferencia."""
    return _recusar_processo_view(
        request,
        pk,
        permission="fluxo.pode_contabilizar",
        status_devolucao=ProcessoStatus.PAGO_EM_CONFERENCIA,
        error_message="Processo #{processo_id} recusado pela Contabilidade e devolvido para a Conferência!",
        redirect_to="painel_contabilizacao",
    )


__all__ = [
    "iniciar_contabilizacao_action",
    "aprovar_contabilizacao_action",
    "recusar_contabilizacao_action",
]
