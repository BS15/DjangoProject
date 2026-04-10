"""Acoes POST da etapa de conferencia."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from fluxo.views.helpers import _iniciar_fila_sessao


@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
@require_POST
def iniciar_conferencia_view(request):
    """Inicializa a fila de trabalho da conferencia na sessao do usuario."""
    return _iniciar_fila_sessao(request, "conferencia_queue", "painel_conferencia", "conferencia_processo")


@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
@require_POST
def aprovar_conferencia_view(request, pk):
    """Mantem compatibilidade da rota de aprovacao direta da conferencia."""
    messages.error(request, "A aprovação direta foi desativada. Abra o processo para realizar a conferência.")
    return redirect("painel_conferencia")


__all__ = ["iniciar_conferencia_view", "aprovar_conferencia_view"]
