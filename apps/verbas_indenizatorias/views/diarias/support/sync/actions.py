"""Acoes de sincronizacao de diarias (POST-only)."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from apps.verbas_indenizatorias.services.diarias_sync import sincronizar_numero_siscac_csv

_SYNC_RESULTS_SESSION_KEY = "sincronizar_diarias_resultados"


@require_POST
@permission_required("pagamentos.pode_sincronizar_diarias_siscac", raise_exception=True)
def sincronizar_diarias_action(request):
    """Processa upload do CSV e sincroniza numero SISCAC de diarias."""
    csv_file = request.FILES.get("siscac_csv")
    if not csv_file:
        messages.error(request, "Nenhum arquivo CSV foi enviado.")
        return redirect("verbas_indenizatorias:sincronizar_diarias")

    resultados = sincronizar_numero_siscac_csv(csv_file)
    if resultados["atualizadas"]:
        messages.success(request, f"{resultados['atualizadas']} diaria(s) sincronizada(s) com sucesso.")
    if resultados["erros"]:
        messages.warning(request, f"Sincronizacao concluida com {len(resultados['erros'])} erro(s).")
    request.session[_SYNC_RESULTS_SESSION_KEY] = resultados

    return redirect("verbas_indenizatorias:sincronizar_diarias")


__all__ = ["sincronizar_diarias_action"]
