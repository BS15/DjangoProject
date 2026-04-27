"""Acoes POST da etapa de contabilizacao."""

from django.contrib.auth.decorators import permission_required
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from pagamentos.domain_models import Processo, ProcessoStatus
from pagamentos.views.helpers import _aprovar_processo_view, _recusar_processo_view


@require_POST
@permission_required("pagamentos.pode_contabilizar", raise_exception=True)
def iniciar_contabilizacao_action(request: HttpRequest) -> HttpResponse:
    """Inicializa a fila de trabalho da contabilizacao na sessao."""
    ids_raw = request.POST.getlist("processo_ids")
    process_ids = [int(pid) for pid in ids_raw if pid.isdigit()]

    if not process_ids:
        messages.warning(request, "Selecione ao menos um processo para iniciar a revisão.")
        return redirect("painel_contabilizacao")

    ids_validos = set(
        Processo.objects.filter(
            id__in=process_ids,
            status__opcao_status__iexact=ProcessoStatus.PAGO_A_CONTABILIZAR,
        ).values_list("id", flat=True)
    )
    fila = [pid for pid in process_ids if pid in ids_validos]

    if not fila:
        messages.warning(request, "Nenhum processo selecionado está elegível para contabilização.")
        return redirect("painel_contabilizacao")

    if len(fila) < len(process_ids):
        messages.info(request, "Alguns processos foram ignorados por não estarem mais na etapa de contabilização.")

    request.session["contabilizacao_queue"] = fila
    request.session.modified = True
    return redirect("contabilizacao_processo", pk=fila[0])


@require_POST
@permission_required("pagamentos.pode_contabilizar", raise_exception=True)
def aprovar_contabilizacao_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Aprova contabilizacao por rota direta e avanca status do processo."""
    return _aprovar_processo_view(
        request,
        pk,
        permission="pagamentos.pode_contabilizar",
        new_status=ProcessoStatus.CONTABILIZADO_CONSELHO,
        success_message="Processo #{processo_id} contabilizado e enviado ao Conselho Fiscal!",
        redirect_to="painel_contabilizacao",
    )


@require_POST
@permission_required("pagamentos.pode_contabilizar", raise_exception=True)
def recusar_contabilizacao_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Recusa contabilizacao e devolve o processo para conferencia."""
    return _recusar_processo_view(
        request,
        pk,
        permission="pagamentos.pode_contabilizar",
        status_devolucao=ProcessoStatus.PAGO_EM_CONFERENCIA,
        error_message="Processo #{processo_id} recusado pela Contabilidade e devolvido para a Conferência!",
        redirect_to="painel_contabilizacao",
    )


__all__ = [
    "iniciar_contabilizacao_action",
    "aprovar_contabilizacao_action",
    "recusar_contabilizacao_action",
]
