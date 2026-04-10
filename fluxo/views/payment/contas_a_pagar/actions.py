"""Acoes POST da etapa de contas a pagar."""

from django.contrib.auth.decorators import permission_required
from django.views.decorators.http import require_POST

from fluxo.views.helpers import _processar_acao_lote


@require_POST
@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
def enviar_para_autorizacao(request):
    """Envia em lote processos elegiveis para autorizacao."""
    return _processar_acao_lote(
        request,
        param_name="processos_selecionados",
        status_origem_esperado="A PAGAR - PENDENTE AUTORIZAÇÃO",
        status_destino="A PAGAR - ENVIADO PARA AUTORIZAÇÃO",
        msg_sucesso="{count} processo(s) enviado(s) para autorização com sucesso.",
        msg_vazio="Nenhum processo foi selecionado.",
        msg_sem_elegiveis='Nenhum dos processos selecionados está com status "{status_origem_esperado}".',
        msg_ignorados=(
            "{count} processo(s) ignorado(s): apenas processos com status "
            '"{status_origem_esperado}" podem ser enviados para autorização.'
        ),
        redirect_to="contas_a_pagar",
    )


__all__ = ["enviar_para_autorizacao"]
