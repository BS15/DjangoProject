"""Sincronização de diárias (integrações externas)."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import redirect


@permission_required("fluxo.pode_sincronizar_diarias_siscac", raise_exception=True)
def sincronizar_diarias(request):
    """Ponto de entrada da sincronização de diárias via SISCAC.

    A integração efetiva é executada por rotina administrativa dedicada.
    """
    messages.info(
        request,
        "Sincronização de diárias registrada. Execute a rotina administrativa para processar os dados do SISCAC.",
    )
    return redirect("diarias_list")


__all__ = ["sincronizar_diarias"]
