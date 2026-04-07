"""Acoes POST da etapa de contabilizacao."""

from django.contrib.auth.decorators import permission_required
from django.views.decorators.http import require_POST

from ...helpers import _aprovar_processo_view, _iniciar_fila_sessao, _recusar_processo_view


@permission_required("processos.pode_contabilizar", raise_exception=True)
@require_POST
def iniciar_contabilizacao_view(request):
    """Inicializa a fila de trabalho da contabilizacao na sessao."""
    return _iniciar_fila_sessao(
        request,
        "contabilizacao_queue",
        "painel_contabilizacao",
        "contabilizacao_processo",
    )


@permission_required("processos.pode_contabilizar", raise_exception=True)
@require_POST
def aprovar_contabilizacao_view(request, pk):
    """Aprova contabilizacao por rota direta e avanca status do processo."""
    return _aprovar_processo_view(
        request,
        pk,
        permission="processos.pode_contabilizar",
        new_status="CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL",
        success_message="Processo #{processo_id} contabilizado e enviado ao Conselho Fiscal!",
        redirect_to="painel_contabilizacao",
    )


@permission_required("processos.pode_contabilizar", raise_exception=True)
@require_POST
def recusar_contabilizacao_view(request, pk):
    """Recusa contabilizacao e devolve o processo para conferencia."""
    return _recusar_processo_view(
        request,
        pk,
        permission="processos.pode_contabilizar",
        status_devolucao="PAGO - EM CONFERÊNCIA",
        error_message="Processo #{processo_id} recusado pela Contabilidade e devolvido para a Conferência!",
        redirect_to="painel_contabilizacao",
    )


__all__ = [
    "iniciar_contabilizacao_view",
    "aprovar_contabilizacao_view",
    "recusar_contabilizacao_view",
]
