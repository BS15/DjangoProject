"""Views de formulários para contas fixas."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render

from credores.forms import ContaFixaForm
from credores.models import ContaFixa


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def add_conta_fixa_view(request):
    """Cadastra nova conta fixa para geração recorrente de faturas."""
    if request.method == "POST":
        form = ContaFixaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Conta fixa cadastrada com sucesso!")
            return redirect("painel_contas_fixas")
        messages.error(request, "Erro ao cadastrar. Verifique os campos.")
    else:
        form = ContaFixaForm()

    return render(request, "contas/add_conta_fixa.html", {"form": form})


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def edit_conta_fixa_view(request, pk):
    """Atualiza dados cadastrais de uma conta fixa existente."""
    conta = get_object_or_404(ContaFixa, pk=pk)
    if request.method == "POST":
        form = ContaFixaForm(request.POST, instance=conta)
        if form.is_valid():
            form.save()
            messages.success(request, "Conta fixa atualizada com sucesso!")
            return redirect("painel_contas_fixas")
        messages.error(request, "Erro ao atualizar. Verifique os campos.")
    else:
        form = ContaFixaForm(instance=conta)

    return render(request, "contas/edit_conta_fixa.html", {"form": form, "conta": conta})