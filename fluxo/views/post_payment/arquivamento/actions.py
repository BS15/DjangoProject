"""Acoes POST da etapa de arquivamento."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from fluxo.domain_models import Processo, ProcessoStatus
from fluxo.views.helpers import (
    ArquivamentoDefinitivoError,
    ArquivamentoSemDocumentosError,
    _executar_arquivamento_definitivo,
)


logger = logging.getLogger(__name__)


@require_POST
@permission_required("fluxo.pode_arquivar", raise_exception=True)
def arquivar_processo_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Executa o arquivamento definitivo de um processo elegivel."""
    processo = get_object_or_404(Processo, id=pk)

    status_atual = processo.status.status_choice if processo.status else ""
    if status_atual.upper() != ProcessoStatus.APROVADO_PENDENTE_ARQUIVAMENTO:
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
