"""Acoes POST da etapa de conselho fiscal."""

from django.contrib.auth.decorators import permission_required
from django.views.decorators.http import require_POST

from ...helpers import _aprovar_processo_view, _recusar_processo_view


@permission_required("processos.pode_auditar_conselho", raise_exception=True)
@require_POST
def aprovar_conselho_view(request, pk):
    """Aprova processo no conselho via rota direta."""
    return _aprovar_processo_view(
        request,
        pk,
        permission="processos.pode_auditar_conselho",
        new_status="APROVADO - PENDENTE ARQUIVAMENTO",
        success_message="Processo #{processo_id} aprovado pelo Conselho e liberado para arquivamento!",
        redirect_to="painel_conselho",
    )


@permission_required("processos.pode_auditar_conselho", raise_exception=True)
@require_POST
def recusar_conselho_view(request, pk):
    """Recusa processo no conselho e devolve para contabilizacao."""
    return _recusar_processo_view(
        request,
        pk,
        permission="processos.pode_auditar_conselho",
        status_devolucao="PAGO - A CONTABILIZAR",
        error_message="Processo #{processo_id} recusado pelo Conselho Fiscal e devolvido para a Contabilidade!",
        redirect_to="painel_conselho",
    )


__all__ = ["aprovar_conselho_view", "recusar_conselho_view"]
