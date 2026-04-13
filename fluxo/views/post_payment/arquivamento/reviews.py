"""Telas de revisao da etapa de arquivamento."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from fluxo.domain_models import Processo


@require_GET
@permission_required("fluxo.pode_arquivar", raise_exception=True)
def arquivar_processo_view(request, pk):
    """Exibe a ficha de conferencia pre-arquivamento de um processo."""
    processo = get_object_or_404(Processo, id=pk)
    status_atual = processo.status.status_choice if processo.status else ""
    elegivel = status_atual.upper() == "APROVADO - PENDENTE ARQUIVAMENTO"

    return render(
        request,
        "fluxo/arquivar_processo.html",
        {
            "processo": processo,
            "elegivel_para_arquivamento": elegivel,
            "pode_interagir": request.user.has_perm("fluxo.pode_arquivar"),
        },
    )


__all__ = ["arquivar_processo_view"]
