"""Acoes POST da etapa de conferencia."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from pagamentos.domain_models import Processo, ProcessoStatus
@require_POST
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def iniciar_conferencia_action(request: HttpRequest) -> HttpResponse:
    """Inicializa a fila de trabalho da conferencia na sessao do usuario."""
    ids_raw = request.POST.getlist("processo_ids")
    process_ids = [int(pid) for pid in ids_raw if pid.isdigit()]

    if not process_ids:
        messages.warning(request, "Selecione ao menos um processo para iniciar a revisão.")
        return redirect("painel_conferencia")

    ids_validos = set(
        Processo.objects.filter(
            id__in=process_ids,
            status__opcao_status__iexact=ProcessoStatus.PAGO_EM_CONFERENCIA,
        ).values_list("id", flat=True)
    )
    fila = [pid for pid in process_ids if pid in ids_validos]

    if not fila:
        messages.warning(request, "Nenhum processo selecionado está elegível para conferência.")
        return redirect("painel_conferencia")

    if len(fila) < len(process_ids):
        messages.info(request, "Alguns processos foram ignorados por não estarem mais na etapa de conferência.")

    request.session["conferencia_queue"] = fila
    request.session.modified = True
    return redirect("conferencia_processo", pk=fila[0])


@require_POST
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def aprovar_conferencia_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Mantem compatibilidade da rota de aprovacao direta da conferencia."""
    messages.error(request, "A aprovação direta foi desativada. Abra o processo para realizar a conferência.")
    return redirect("painel_conferencia")


__all__ = ["iniciar_conferencia_action", "aprovar_conferencia_action"]
