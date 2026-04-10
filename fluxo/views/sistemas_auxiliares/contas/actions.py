"""Views de ações para contas fixas."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from credores.models import ContaFixa, FaturaMensal
from fluxo.models import Processo


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def vincular_processo_fatura_view(request, fatura_id):
    """Vincula manualmente uma fatura mensal a um processo existente."""
    fatura = get_object_or_404(FaturaMensal, id=fatura_id)
    mes = request.POST.get("mes", "")
    ano = request.POST.get("ano", "")

    if request.method == "POST":
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


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def excluir_conta_fixa_view(request, pk):
    """Exclui conta fixa mediante confirmação por requisição POST."""
    conta = get_object_or_404(ContaFixa, pk=pk)
    if request.method == "POST":
        conta.delete()
        messages.success(request, "Conta fixa excluída com sucesso!")
    return redirect("painel_contas_fixas")