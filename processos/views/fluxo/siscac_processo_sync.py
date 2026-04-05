"""Views dedicadas à sincronização SISCAC."""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from ...models import Processo
from ...utils import parse_siscac_report, sync_siscac_payments


@require_GET
def sincronizar_siscac(request):
    """Renderiza o painel de sincronização SISCAC."""
    return render(request, "fluxo/sincronizar_siscac.html", {})


@require_POST
def sincronizar_siscac_manual_action(request):
    """Processa sincronização manual de pares processo|SISCAC selecionados."""
    force_sync_ids = request.POST.getlist("force_sync_ids")
    count = 0
    errors = 0

    for item in force_sync_ids:
        try:
            processo_id, siscac_pg = item.split("|", 1)
            updated = Processo.objects.filter(id=int(processo_id)).update(n_pagamento_siscac=siscac_pg)
            if updated:
                count += 1
            else:
                errors += 1
        except Exception:
            errors += 1

    if count:
        messages.success(request, f"{count} processo(s) sincronizado(s) com sucesso.")
    if errors:
        messages.error(request, f"{errors} item(ns) não puderam ser sincronizados.")
    return redirect("sincronizar_siscac")


@require_POST
def sincronizar_siscac_auto_action(request):
    """Processa upload do PDF SISCAC e executa sincronização automática."""
    pdf_file = request.FILES.get("siscac_pdf")
    if not pdf_file or not pdf_file.name.lower().endswith(".pdf"):
        messages.error(request, "Nenhum arquivo ou PDF inválido enviado.")
        return redirect("sincronizar_siscac")

    try:
        extracted = parse_siscac_report(pdf_file)
        results = sync_siscac_payments(extracted)
        return render(request, "fluxo/sincronizar_siscac.html", {"resultados": results})
    except Exception as e:
        messages.error(request, f"Erro ao processar o relatório SISCAC: {e}")
        return redirect("sincronizar_siscac")


__all__ = [
    "sincronizar_siscac",
    "sincronizar_siscac_manual_action",
    "sincronizar_siscac_auto_action",
]
