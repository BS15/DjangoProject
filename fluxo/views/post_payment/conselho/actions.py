"""Acoes POST da etapa de conselho fiscal."""

from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_POST

from fluxo.views.helpers import _aprovar_processo_view, _recusar_processo_view


@require_POST
@permission_required("fluxo.pode_auditar_conselho", raise_exception=True)
def aprovar_conselho_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Aprova processo no conselho via rota direta."""
    return _aprovar_processo_view(
        request,
        pk,
        permission="fluxo.pode_auditar_conselho",
        new_status="APROVADO - PENDENTE ARQUIVAMENTO",
        success_message="Processo #{processo_id} aprovado pelo Conselho e liberado para arquivamento!",
        redirect_to="painel_conselho",
    )


@require_POST
@permission_required("fluxo.pode_auditar_conselho", raise_exception=True)
def recusar_conselho_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Recusa processo no conselho e devolve para contabilizacao."""
    return _recusar_processo_view(
        request,
        pk,
        permission="fluxo.pode_auditar_conselho",
        status_devolucao="PAGO - A CONTABILIZAR",
        error_message="Processo #{processo_id} recusado pelo Conselho Fiscal e devolvido para a Contabilidade!",
        redirect_to="painel_conselho",
    )


__all__ = ["aprovar_conselho_action", "recusar_conselho_action"]
