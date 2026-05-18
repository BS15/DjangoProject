"""Acoes de devolucao (POST views)."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.pagamentos.forms import DevolucaoForm
from apps.pagamentos.domain_models import Processo


@require_POST
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def registrar_devolucao_action(request: HttpRequest, processo_id: int) -> HttpResponse:
    """Persiste devolucao vinculada ao processo a partir do POST do formulario."""
    processo = get_object_or_404(Processo, id=processo_id)
    form = DevolucaoForm(request.POST, request.FILES)

    if form.is_valid():
        devolucao = form.save(commit=False)
        devolucao.processo = processo
        devolucao.save()
        messages.success(request, "Devolução registrada com sucesso.")
        return redirect("pagamentos:process_detail", processo.id)

    messages.error(request, "Não foi possível registrar a devolução. Verifique os dados informados.")
    return redirect("pagamentos:registrar_devolucao_action", processo_id=processo.id)


__all__ = [
    "registrar_devolucao_action",
]
