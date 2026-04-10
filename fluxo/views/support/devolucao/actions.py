"""Acoes de devolucao (POST views)."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from fluxo.forms import DevolucaoForm
from fluxo.models import Processo


@require_POST
@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def registrar_devolucao_action(request: HttpRequest, processo_id: int) -> HttpResponse:
    """Persiste devolucao vinculada ao processo a partir do POST do formulario."""
    processo = get_object_or_404(Processo, id=processo_id)
    form = DevolucaoForm(request.POST, request.FILES)

    if form.is_valid():
        devolucao = form.save(commit=False)
        devolucao.processo = processo
        devolucao.save()
        messages.success(request, "Devolução registrada com sucesso.")
        return redirect("process_detail", processo.id)

    return render(request, "fluxo/add_devolucao.html", {"form": form, "processo": processo})


__all__ = [
    "registrar_devolucao_action",
]
