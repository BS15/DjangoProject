"""Acoes POST da etapa de autorizacao."""

from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_POST

from fluxo.domain_models import ProcessoStatus
from fluxo.views.helpers import _processar_acao_lote, _recusar_processo_view


@require_POST
@permission_required("fluxo.pode_autorizar_pagamento", raise_exception=True)
def autorizar_pagamento(request: HttpRequest) -> HttpResponse:
    """Autoriza em lote processos selecionados para A PAGAR - AUTORIZADO."""
    return _processar_acao_lote(
        request,
        param_name="processos_selecionados",
        status_origem_esperado=ProcessoStatus.A_PAGAR_ENVIADO_PARA_AUTORIZACAO,
        status_destino=ProcessoStatus.A_PAGAR_AUTORIZADO,
        msg_sucesso="{count} pagamento(s) autorizado(s) com sucesso!",
        msg_vazio="Nenhum processo foi selecionado para autorização.",
        msg_sem_elegiveis='Ação negada: nenhum processo selecionado estava no status "{status_origem_esperado}".',
        msg_ignorados="{count} processo(s) ignorado(s) por estarem em outro estágio do fluxo.",
        redirect_to="painel_autorizacao",
    )


@require_POST
@permission_required("fluxo.pode_autorizar_pagamento", raise_exception=True)
def recusar_autorizacao_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Recusa autorizacao de um processo e devolve ao fluxo de correcao."""
    return _recusar_processo_view(
        request,
        pk,
        permission="fluxo.pode_autorizar_pagamento",
        status_devolucao=ProcessoStatus.AGUARDANDO_LIQUIDACAO,
        error_message="Processo #{processo_id} não autorizado e devolvido com pendência!",
        redirect_to="painel_autorizacao",
    )


__all__ = ["autorizar_pagamento", "recusar_autorizacao_action"]
