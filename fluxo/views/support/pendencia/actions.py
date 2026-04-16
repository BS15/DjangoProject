"""Acoes POST do painel de pendencias."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import DatabaseError, transaction
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from fluxo.domain_models import Pendencia, StatusChoicesPendencias


PENDENCIA_ACAO_STATUS = {
    "resolver": "RESOLVIDO",
    "excluir": "EXCLUÍDO",
}


@require_POST
@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def atualizar_pendencias_lote_action(request):
    """Atualiza status de pendências selecionadas em lote sem exclusão física."""
    acao_lote = (request.POST.get("acao_lote") or "").strip().lower()
    ids_selecionados = [pid for pid in request.POST.getlist("pendencias_selecionadas") if pid]
    pendencia_id_unica = (request.POST.get("pendencia_id") or "").strip()

    if not ids_selecionados and pendencia_id_unica:
        ids_selecionados = [pendencia_id_unica]

    if not ids_selecionados:
        messages.warning(request, "Selecione ao menos uma pendência para executar a ação em lote.")
        return redirect("painel_pendencias")

    if acao_lote not in PENDENCIA_ACAO_STATUS:
        messages.error(request, "Ação em lote inválida para pendências.")
        return redirect("painel_pendencias")

    status_destino = PENDENCIA_ACAO_STATUS[acao_lote]
    status_obj, _ = StatusChoicesPendencias.objects.get_or_create(
        status_choice__iexact=status_destino,
        defaults={"status_choice": status_destino},
    )

    pendencias = Pendencia.objects.filter(id__in=ids_selecionados).select_related("status")
    total_encontradas = pendencias.count()
    total_nao_encontradas = len(ids_selecionados) - total_encontradas
    total_atualizadas = 0
    total_inalteradas = 0

    try:
        with transaction.atomic():
            for pendencia in pendencias:
                if pendencia.status_id == status_obj.id:
                    total_inalteradas += 1
                    continue
                pendencia.status = status_obj
                pendencia.save(update_fields=["status"])
                total_atualizadas += 1
    except (DatabaseError, TypeError, ValueError):
        messages.error(request, "Erro interno ao atualizar pendências em lote.")
        return redirect("painel_pendencias")

    if total_atualizadas:
        messages.success(
            request,
            f"{total_atualizadas} pendência(s) marcada(s) como {status_destino}.",
        )
    if total_inalteradas:
        messages.info(request, f"{total_inalteradas} pendência(s) já estavam com esse status.")
    if total_nao_encontradas:
        messages.warning(request, f"{total_nao_encontradas} pendência(s) não foram encontradas.")

    return redirect("painel_pendencias")


__all__ = ["atualizar_pendencias_lote_action"]