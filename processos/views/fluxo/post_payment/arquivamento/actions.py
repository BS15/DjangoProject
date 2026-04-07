"""Acoes POST da etapa de arquivamento."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .....models import Processo
from ...helpers import _executar_arquivamento_definitivo


@permission_required("processos.pode_arquivar", raise_exception=True)
@require_POST
def arquivar_processo_action(request, pk):
    """Executa o arquivamento definitivo de um processo elegivel."""
    processo = get_object_or_404(Processo, id=pk)

    status_atual = processo.status.status_choice if processo.status else ""
    if status_atual.upper() != "APROVADO - PENDENTE ARQUIVAMENTO":
        messages.error(request, f"Processo #{processo.id} não está no status correto para arquivamento.")
        return redirect("painel_arquivamento")

    sucesso = _executar_arquivamento_definitivo(processo, request.user)
    if not sucesso:
        messages.error(request, f"Processo #{processo.id} não possui documentos para arquivar.")
        return redirect("painel_arquivamento")

    messages.success(request, f"Processo #{processo.id} arquivado definitivamente com sucesso!")
    return redirect("painel_arquivamento")


__all__ = ["arquivar_processo_action"]
