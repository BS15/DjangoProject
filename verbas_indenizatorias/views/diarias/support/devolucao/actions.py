"""Acoes de devolucao de diarias (POST-only)."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from verbas_indenizatorias.forms import DevolucaoDiariaForm
from verbas_indenizatorias.models import Diaria
from verbas_indenizatorias.services.devolucao_diarias import registrar_devolucao_diaria

logger = logging.getLogger(__name__)


@require_POST
@permission_required("verbas_indenizatorias.pode_gerenciar_diarias", raise_exception=True)
def registrar_devolucao_diaria_action(request, pk):
    """Persiste devolucao vinculada a diaria a partir do POST do formulario."""
    diaria = get_object_or_404(Diaria.objects.select_for_update(), pk=pk)
    form = DevolucaoDiariaForm(request.POST)

    if not form.is_valid():
        for field_errors in form.errors.values():
            for err in field_errors:
                messages.error(request, err)
        return redirect("registrar_devolucao_diaria", pk=pk)

    try:
        devolucao = registrar_devolucao_diaria(diaria, form, request.user)
    except Exception as exc:
        messages.error(request, f"Dados invalidos: {exc}")
        return redirect("registrar_devolucao_diaria", pk=pk)

    logger.info(
        "mutation=registrar_devolucao_diaria diaria_id=%s devolucao_id=%s user_id=%s valor=%s",
        diaria.pk,
        devolucao.pk,
        request.user.pk,
        devolucao.valor_devolvido,
    )
    messages.success(request, f"Devolucao de R$ {devolucao.valor_devolvido} registrada com sucesso.")
    return redirect("gerenciar_diaria", pk=pk)


__all__ = ["registrar_devolucao_diaria_action"]
