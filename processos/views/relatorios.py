from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from processos.models import Processo, Diaria, RetencaoImposto
from processos.filters import ProcessoFilter, DiariaFilter, RetencaoIndividualFilter
from processos.utils_relatorios import gerar_csv_relatorio


@login_required
def painel_relatorios_view(request):
    tipo = request.GET.get('tipo', 'processos')
    exportar = request.GET.get('exportar')

    if tipo == 'processos':
        filtro = ProcessoFilter(request.GET, queryset=Processo.objects.all().order_by('-id'))
    elif tipo == 'diarias':
        filtro = DiariaFilter(request.GET, queryset=Diaria.objects.all().order_by('-id'))
    elif tipo == 'impostos':
        filtro = RetencaoIndividualFilter(request.GET, queryset=RetencaoImposto.objects.all().order_by('-id'))
    else:
        filtro = None

    if exportar == 'csv' and filtro:
        return gerar_csv_relatorio(filtro.qs, tipo)

    context = {'tipo': tipo, 'filtro': filtro}
    return render(request, 'relatorios/painel.html', context)
