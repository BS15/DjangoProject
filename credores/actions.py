"""Actions (POST-only) do domínio de credores."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from credores.forms import CredorEditForm, CredorForm
from credores.models import Credor


@require_POST
@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def add_credor_action(request):
    """Cria credor a partir de payload completo de cadastro."""
    form = CredorForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Erro ao cadastrar. Verifique os campos.")
        return redirect("add_credor_view")

    credor = form.save()
    messages.success(request, "Credor cadastrado com sucesso!")
    return redirect("gerenciar_credor_view", pk=credor.pk)


@require_POST
@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def edit_credor_action(request, pk):
    """Atualiza campos operacionais do credor mantendo CPF/CNPJ imutável."""
    credor = get_object_or_404(Credor, pk=pk)
    form = CredorEditForm(request.POST, instance=credor)

    if not form.is_valid():
        messages.error(request, "Erro ao atualizar. Verifique os campos.")
        return redirect("gerenciar_credor_view", pk=credor.pk)

    form.save()
    messages.success(request, "Dados cadastrais atualizados com sucesso.")
    return redirect("gerenciar_credor_view", pk=credor.pk)


@require_POST
@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def toggle_status_credor_action(request, pk):
    """Alterna status ativo/bloqueado do credor por ação isolada."""
    credor = get_object_or_404(Credor, pk=pk)
    credor.ativo = not credor.ativo
    credor.save(update_fields=["ativo"])

    if credor.ativo:
        messages.success(request, "Credor restaurado para status regular.")
    else:
        messages.warning(request, "Credor bloqueado para novos pagamentos.")

    return redirect("gerenciar_credor_view", pk=credor.pk)
