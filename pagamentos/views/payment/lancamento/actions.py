"""Acoes POST da etapa de lancamento bancario."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from pagamentos.domain_models import ProcessoStatus
from pagamentos.views.helpers import _processar_acao_lote


@require_POST
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def separar_para_lancamento_bancario_action(request: HttpRequest) -> HttpResponse:
    """Armazena em sessao os processos selecionados para lancamento."""
    selecionados = request.POST.getlist("processos_selecionados")

    if not selecionados:
        messages.warning(request, "Nenhum processo foi selecionado.")
        return redirect("contas_a_pagar")

    request.session["processos_lancamento"] = [int(pid) for pid in selecionados]
    return redirect("lancamento_bancario")


@require_POST
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def marcar_como_lancado_action(request: HttpRequest) -> HttpResponse:
    """Move processo para LANCADO - AGUARDANDO COMPROVANTE."""
    return _processar_acao_lote(
        request,
        param_name="processo_id",
        status_origem_esperado=ProcessoStatus.A_PAGAR_AUTORIZADO,
        status_destino=ProcessoStatus.LANCADO_AGUARDANDO_COMPROVANTE,
        msg_sucesso="Processo #{processo_id} marcado como lançado com sucesso.",
        msg_vazio="ID de processo inválido.",
        msg_sem_elegiveis=(
            "Ação negada para o Processo #{processo_id}: o status atual não permite marcar como lançado."
        ),
        msg_ignorados="{count} processo(s) ignorado(s) por estarem em outro estágio do fluxo.",
        redirect_to="lancamento_bancario",
    )


@require_POST
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def desmarcar_lancamento_action(request: HttpRequest) -> HttpResponse:
    """Reverte lancamento bancario para A PAGAR - AUTORIZADO."""
    return _processar_acao_lote(
        request,
        param_name="processo_id",
        status_origem_esperado=ProcessoStatus.LANCADO_AGUARDANDO_COMPROVANTE,
        status_destino=ProcessoStatus.A_PAGAR_AUTORIZADO,
        msg_sucesso="Lançamento do Processo #{processo_id} desmarcado.",
        msg_vazio="ID de processo inválido.",
        msg_sem_elegiveis=(
            "Ação negada para o Processo #{processo_id}: o status atual não permite desmarcar lançamento."
        ),
        msg_ignorados="{count} processo(s) ignorado(s) por estarem em outro estágio do fluxo.",
        redirect_to="lancamento_bancario",
    )


__all__ = [
    "separar_para_lancamento_bancario_action",
    "marcar_como_lancado_action",
    "desmarcar_lancamento_action",
]
