"""Acoes POST da etapa de lancamento bancario."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from ...helpers import _processar_acao_lote


@require_POST
@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def separar_para_lancamento_bancario(request):
    """Armazena em sessao os processos selecionados para lancamento."""
    selecionados = request.POST.getlist("processos_selecionados")

    if not selecionados:
        messages.warning(request, "Nenhum processo foi selecionado.")
        return redirect("contas_a_pagar")

    request.session["processos_lancamento"] = [int(pid) for pid in selecionados]
    return redirect("lancamento_bancario")


@require_POST
@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def marcar_como_lancado(request):
    """Move processo para LANCADO - AGUARDANDO COMPROVANTE."""
    return _processar_acao_lote(
        request,
        param_name="processo_id",
        status_origem_esperado="A PAGAR - AUTORIZADO",
        status_destino="LANÇADO - AGUARDANDO COMPROVANTE",
        msg_sucesso="Processo #{processo_id} marcado como lançado com sucesso.",
        msg_vazio="ID de processo inválido.",
        msg_sem_elegiveis=(
            "Ação negada para o Processo #{processo_id}: o status atual não permite marcar como lançado."
        ),
        msg_ignorados="{count} processo(s) ignorado(s) por estarem em outro estágio do fluxo.",
        redirect_to="lancamento_bancario",
    )


@require_POST
@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def desmarcar_lancamento(request):
    """Reverte lancamento bancario para A PAGAR - AUTORIZADO."""
    return _processar_acao_lote(
        request,
        param_name="processo_id",
        status_origem_esperado="LANÇADO - AGUARDANDO COMPROVANTE",
        status_destino="A PAGAR - AUTORIZADO",
        msg_sucesso="Lançamento do Processo #{processo_id} desmarcado.",
        msg_vazio="ID de processo inválido.",
        msg_sem_elegiveis=(
            "Ação negada para o Processo #{processo_id}: o status atual não permite desmarcar lançamento."
        ),
        msg_ignorados="{count} processo(s) ignorado(s) por estarem em outro estágio do fluxo.",
        redirect_to="lancamento_bancario",
    )


__all__ = [
    "separar_para_lancamento_bancario",
    "marcar_como_lancado",
    "desmarcar_lancamento",
]
