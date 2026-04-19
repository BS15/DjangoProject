"""Telas de revisao da etapa de contabilizacao."""

from django.contrib.auth.decorators import permission_required

from fluxo.domain_models import ProcessoStatus
from fluxo.views.helpers import _processo_fila_detalhe_view


@permission_required("fluxo.pode_contabilizar", raise_exception=True)
def contabilizacao_processo_view(request, pk):
    """Revisa processo na etapa de contabilizacao com acoes de aprovar/recusar."""
    return _processo_fila_detalhe_view(
        request,
        pk,
        permission="fluxo.pode_contabilizar",
        queue_key="contabilizacao_queue",
        fallback_view="painel_contabilizacao",
        current_view="contabilizacao_processo",
        template_name="fluxo/contabilizacao_processo.html",
        approve_action="aprovar",
        approve_status=ProcessoStatus.CONTABILIZADO_CONSELHO,
        approve_message="Processo #{processo_id} contabilizado e enviado ao Conselho Fiscal!",
        save_action="salvar",
        save_message="Alterações do Processo #{processo_id} salvas.",
        reject_action="rejeitar",
        reject_status=ProcessoStatus.PAGO_EM_CONFERENCIA,
        reject_message="Processo #{processo_id} recusado pela Contabilidade e devolvido para a Conferência!",
        editable=True,
    )


__all__ = ["contabilizacao_processo_view"]
