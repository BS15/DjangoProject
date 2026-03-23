import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse

from processos.models import FaturaMensal, Processo
from processos.utils_contas import gerar_faturas_do_mes


@login_required
def painel_contas_fixas_view(request):
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
    }
    return render(request, 'contas/painel_contas_fixas.html', context)


@login_required
def vincular_processo_fatura_view(request, fatura_id):
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

