import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.urls import reverse

from processos.models import FaturaMensal, Processo, ContaFixa
from processos.forms import ContaFixaForm
from processos.utils.utils_contas import gerar_faturas_do_mes


@permission_required("processos.acesso_backoffice", raise_exception=True)
def painel_contas_fixas_view(request):
    """Exibe painel mensal de contas fixas e faturas geradas automaticamente."""
    hoje = datetime.date.today()
    mes = int(request.GET.get('mes', hoje.month))
    ano = int(request.GET.get('ano', hoje.year))

    gerar_faturas_do_mes(ano, mes)

    data_ref = datetime.date(ano, mes, 1)
    faturas = (
        FaturaMensal.objects
        .filter(mes_referencia=data_ref)
        .select_related('conta_fixa__credor', 'processo_vinculado')
        .order_by('conta_fixa__dia_vencimento')
    )

    context = {
        'faturas': faturas,
        'mes': mes,
        'ano': ano,
        'contas_fixas': ContaFixa.objects.select_related('credor').order_by('credor__nome', 'referencia'),
    }
    return render(request, 'contas/painel_contas_fixas.html', context)


@permission_required("processos.acesso_backoffice", raise_exception=True)
def vincular_processo_fatura_view(request, fatura_id):
    """Vincula manualmente uma fatura mensal a um processo existente."""
    fatura = get_object_or_404(FaturaMensal, id=fatura_id)
    mes = request.POST.get('mes', '')
    ano = request.POST.get('ano', '')

    if request.method == 'POST':
        processo_id = request.POST.get('processo_id')
        if processo_id:
            try:
                processo = get_object_or_404(Processo, id=int(processo_id))
                fatura.processo_vinculado = processo
                fatura.save()
            except (ValueError, TypeError):
                pass

    redirect_url = reverse('painel_contas_fixas')
    if mes and ano:
        redirect_url += f"?mes={mes}&ano={ano}"
    return redirect(redirect_url)


@permission_required("processos.acesso_backoffice", raise_exception=True)
def add_conta_fixa_view(request):
    """Cadastra nova conta fixa para geração recorrente de faturas."""
    if request.method == 'POST':
        form = ContaFixaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Conta fixa cadastrada com sucesso!")
            return redirect('painel_contas_fixas')
        else:
            messages.error(request, "Erro ao cadastrar. Verifique os campos.")
    else:
        form = ContaFixaForm()

    return render(request, 'contas/add_conta_fixa.html', {'form': form})


@permission_required("processos.acesso_backoffice", raise_exception=True)
def edit_conta_fixa_view(request, pk):
    """Atualiza dados cadastrais de uma conta fixa existente."""
    conta = get_object_or_404(ContaFixa, pk=pk)
    if request.method == 'POST':
        form = ContaFixaForm(request.POST, instance=conta)
        if form.is_valid():
            form.save()
            messages.success(request, "Conta fixa atualizada com sucesso!")
            return redirect('painel_contas_fixas')
        else:
            messages.error(request, "Erro ao atualizar. Verifique os campos.")
    else:
        form = ContaFixaForm(instance=conta)

    return render(request, 'contas/edit_conta_fixa.html', {'form': form, 'conta': conta})


@permission_required("processos.acesso_backoffice", raise_exception=True)
def excluir_conta_fixa_view(request, pk):
    """Exclui conta fixa mediante confirmação por requisição POST."""
    conta = get_object_or_404(ContaFixa, pk=pk)
    if request.method == 'POST':
        conta.delete()
        messages.success(request, "Conta fixa excluída com sucesso!")
    return redirect('painel_contas_fixas')

