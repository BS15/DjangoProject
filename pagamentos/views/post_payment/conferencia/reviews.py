"""Telas de revisao da etapa de conferencia."""

from django.contrib.auth.decorators import permission_required

from pagamentos.domain_models import ProcessoStatus
from pagamentos.views.helpers import _processo_fila_detalhe_view


@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def conferencia_processo_view(request, pk):
    """Orquestra a revisao de um processo na etapa de conferencia."""
    return _processo_fila_detalhe_view(
        request,
        pk,
        permission="pagamentos.operador_contas_a_pagar",
        queue_key="conferencia_queue",
        fallback_view="painel_conferencia",
        current_view="conferencia_processo",
        template_name="pagamentos/conferencia_processo.html",
        approve_action="confirmar",
        approve_status=ProcessoStatus.PAGO_A_CONTABILIZAR,
        approve_message="Processo #{processo_id} confirmado na conferência e enviado para Contabilização!",
        save_action="salvar",
        save_message="Alterações do Processo #{processo_id} salvas.",
        editable=True,
        lock_documents=True,
    )


__all__ = ["conferencia_processo_view"]
