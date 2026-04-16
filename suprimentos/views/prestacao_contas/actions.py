"""Views de acoes da etapa de prestacao de contas de suprimentos."""

from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from suprimentos.models import SuprimentoDeFundos
from ..helpers import _atualizar_status_apos_fechamento, _suprimento_encerrado
from suprimentos.forms import DespesaSuprimentoForm


@require_POST
@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def adicionar_despesa_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Registra manualmente uma despesa de suprimento a partir de dados do POST."""
    suprimento: Any = get_object_or_404(SuprimentoDeFundos, id=pk)

    if _suprimento_encerrado(suprimento):
        messages.error(request, "Este suprimento já foi encerrado e não pode receber novas despesas.")
        return redirect("gerenciar_suprimento_view", pk=suprimento.id)

    form = DespesaSuprimentoForm(request.POST, request.FILES)
    if form.is_valid():
        despesa = form.save(commit=False)
        despesa.suprimento = suprimento
        despesa.save()
        messages.success(request, "Despesa e documento anexados com sucesso!")
        return redirect("gerenciar_suprimento_view", pk=suprimento.id)
    else:
        messages.error(request, "Verifique os campos da despesa e tente novamente.")
        return redirect("adicionar_despesa_view", pk=suprimento.id)


@require_POST
@permission_required("suprimentos.acesso_backoffice", raise_exception=True)
def fechar_suprimento_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Encerra a prestacao de contas e avanca o processo vinculado para conferencia."""
    suprimento: Any = get_object_or_404(SuprimentoDeFundos, id=pk)

    if _suprimento_encerrado(suprimento):
        messages.warning(request, f"Suprimento #{suprimento.id} já está encerrado.")
        return redirect("suprimentos_list")

    _atualizar_status_apos_fechamento(suprimento)
    messages.success(
        request,
        f"Prestação de contas do suprimento #{suprimento.id} encerrada e enviada para Conferência!",
    )
    return redirect("suprimentos_list")


__all__ = ["adicionar_despesa_action", "fechar_suprimento_action"]
