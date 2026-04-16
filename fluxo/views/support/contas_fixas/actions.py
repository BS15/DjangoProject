"""Views de ações para contas fixas."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from credores.models import ContaFixa, FaturaMensal
from fluxo.models import Processo

from .forms import ContaFixaForm


@require_POST
@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def add_conta_fixa_action(request: HttpRequest) -> HttpResponse:
    """Persiste nova conta fixa."""
    form = ContaFixaForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Conta fixa cadastrada com sucesso!")
    else:
        messages.error(request, "Erro ao cadastrar. Verifique os campos.")
    return redirect("painel_contas_fixas")


@require_POST
@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def edit_conta_fixa_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Atualiza dados cadastrais de uma conta fixa existente."""
    conta = get_object_or_404(ContaFixa, pk=pk)
    form = ContaFixaForm(request.POST, instance=conta)
    if form.is_valid():
        form.save()
        messages.success(request, "Conta fixa atualizada com sucesso!")
    else:
        messages.error(request, "Erro ao atualizar. Verifique os campos.")
    return redirect("painel_contas_fixas")


@require_POST
@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def vincular_processo_fatura_action(request: HttpRequest, fatura_id: int) -> HttpResponse:
    """Vincula manualmente uma fatura mensal a um processo existente."""
    fatura = get_object_or_404(FaturaMensal, id=fatura_id)
    mes = request.POST.get("mes", "")
    ano = request.POST.get("ano", "")

    processo_id = request.POST.get("processo_id")
    if processo_id:
        try:
            processo = get_object_or_404(Processo, id=int(processo_id))
            fatura.processo_vinculado = processo
            fatura.save()
        except (ValueError, TypeError):
            messages.error(request, "ID de processo inválido para vinculação da fatura.")

    redirect_url = reverse("painel_contas_fixas")
    if mes and ano:
        redirect_url += f"?mes={mes}&ano={ano}"
    return redirect(redirect_url)


@require_POST
@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def excluir_conta_fixa_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Exclui conta fixa mediante confirmação por requisição POST."""
    conta = get_object_or_404(ContaFixa, pk=pk)
    conta.delete()
    messages.success(request, "Conta fixa excluída com sucesso!")
    return redirect("painel_contas_fixas")


__all__ = [
    "add_conta_fixa_action",
    "edit_conta_fixa_action",
    "vincular_processo_fatura_action",
    "excluir_conta_fixa_action",
]
