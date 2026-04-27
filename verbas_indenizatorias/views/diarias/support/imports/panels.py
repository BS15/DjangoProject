"""Paineis de importacao de diarias (GET-only)."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
@permission_required("pagamentos.pode_importar_diarias", raise_exception=True)
def importar_diarias_view(request):
    """Renderiza painel de importacao preservando modo de solicitacao assinada em sessao."""
    context = {
        "modo_solicitacao_assinada": bool(request.session.get("importar_diarias_modo_assinado", False)),
    }
    return render(request, "verbas/importar_diarias.html", context)


__all__ = ["importar_diarias_view"]
