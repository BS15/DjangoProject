"""Acoes POST da etapa de arquivamento."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .....models import Processo
from ...helpers import (
    ArquivamentoDefinitivoError,
    ArquivamentoSemDocumentosError,
    _executar_arquivamento_definitivo,
)


logger = logging.getLogger(__name__)


@permission_required("processos.pode_arquivar", raise_exception=True)
@require_POST
def arquivar_processo_action(request, pk):
    """Executa o arquivamento definitivo de um processo elegivel."""
    processo = get_object_or_404(Processo, id=pk)

    status_atual = processo.status.status_choice if processo.status else ""
    if status_atual.upper() != "APROVADO - PENDENTE ARQUIVAMENTO":
        messages.error(request, f"Processo #{processo.id} não está no status correto para arquivamento.")
        return redirect("painel_arquivamento")

    try:
        _executar_arquivamento_definitivo(processo, request.user)
    except ArquivamentoSemDocumentosError:
        messages.error(request, f"Processo #{processo.id} não possui documentos para arquivar.")
        return redirect("painel_arquivamento")
    except ArquivamentoDefinitivoError as exc:
        logger.exception("Falha de arquivamento definitivo do processo %s", processo.id)
        messages.error(
            request,
            f"Falha ao arquivar o processo #{processo.id}. Detalhe técnico: {exc}",
        )
        return redirect("painel_arquivamento")

    messages.success(request, f"Processo #{processo.id} arquivado definitivamente com sucesso!")
    return redirect("painel_arquivamento")


__all__ = ["arquivar_processo_action"]
