"""Acoes de importacao de diarias (POST-only)."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from verbas_indenizatorias.services.diarias_importacao import (
    confirmar_diarias_lote_com_modo,
    preview_diarias_lote,
)

_PREVIEW_SESSION_KEY = "importar_diarias_preview"
_MODE_SESSION_KEY = "importar_diarias_modo_assinado"


@require_POST
@permission_required("pagamentos.pode_importar_diarias", raise_exception=True)
def importar_diarias_action(request):
    """Processa preview, confirmacao e cancelamento da importacao de diarias."""
    action = request.POST.get("action")

    if action == "confirmar":
        preview_items = request.session.pop(_PREVIEW_SESSION_KEY, None)
        modo_assinado = bool(request.session.pop(_MODE_SESSION_KEY, False))

        if not isinstance(preview_items, list) or not preview_items:
            messages.error(request, "Sessao expirada ou previa nao encontrada. Por favor, importe o arquivo novamente.")
            return redirect("importar_diarias")

        resultados = confirmar_diarias_lote_com_modo(
            preview_items,
            request.user,
            solicitacao_assinada=modo_assinado,
        )
        return render(
            request,
            "verbas/importar_diarias.html",
            {
                "resultados": resultados,
                "modo_solicitacao_assinada": modo_assinado,
            },
        )

    if action == "cancelar":
        request.session.pop(_PREVIEW_SESSION_KEY, None)
        request.session.pop(_MODE_SESSION_KEY, None)
        return redirect("importar_diarias")

    if request.FILES.get("csv_file"):
        resultado_preview = preview_diarias_lote(request.FILES["csv_file"])
        modo_assinado = request.POST.get("modo_solicitacao_assinada") == "on"
        request.session[_PREVIEW_SESSION_KEY] = resultado_preview["preview"]
        request.session[_MODE_SESSION_KEY] = modo_assinado
        return render(
            request,
            "verbas/importar_diarias.html",
            {
                "preview": resultado_preview["preview"],
                "erros_preview": resultado_preview["erros"],
                "modo_solicitacao_assinada": modo_assinado,
            },
        )

    messages.error(request, "Nenhum arquivo CSV foi enviado para importacao.")
    return redirect("importar_diarias")


__all__ = ["importar_diarias_action"]
