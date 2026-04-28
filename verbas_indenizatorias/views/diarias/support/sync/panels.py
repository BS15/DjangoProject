"""Paineis de sincronizacao de diarias (GET-only)."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
@permission_required("pagamentos.pode_sincronizar_diarias_siscac", raise_exception=True)
def sincronizar_diarias_view(request):
    """Renderiza painel de sincronizacao de numeros SISCAC de diarias."""
    resultados = request.session.pop("sincronizar_diarias_resultados", None)
    return render(request, "verbas/sincronizar_diarias.html", {"resultados": resultados})


__all__ = ["sincronizar_diarias_view"]
