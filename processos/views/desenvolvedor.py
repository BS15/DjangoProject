import csv

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from processos.utils_import import importar_contas_fixas_csv, importar_credores_csv


@login_required
def painel_importacao_view(request):
    context = {}
    if request.method == 'POST':
        if 'importar_credores' in request.POST:
            if 'file_credores' not in request.FILES:
                context['resultados'] = {'sucessos': 0, 'erros': ['Nenhum arquivo foi enviado.']}
            else:
                resultados = importar_credores_csv(request.FILES['file_credores'])
                context['resultados'] = resultados
            context['tipo_importacao'] = 'Credores'
        elif 'importar_contas' in request.POST:
            if 'file_contas' not in request.FILES:
                context['resultados'] = {'sucessos': 0, 'erros': ['Nenhum arquivo foi enviado.']}
            else:
                resultados = importar_contas_fixas_csv(request.FILES['file_contas'])
                context['resultados'] = resultados
            context['tipo_importacao'] = 'Contas Fixas'
    return render(request, 'processos/painel_importacao.html', context)


@login_required
def download_template_csv_credores(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="template_credores.csv"'
    writer = csv.writer(response)
    writer.writerow(['NOME', 'CPF_CNPJ'])
    return response


@login_required
def download_template_csv_contas(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="template_contas_fixas.csv"'
    writer = csv.writer(response)
    writer.writerow(['NOME_CREDOR', 'DIA_VENCIMENTO', 'DETALHAMENTO'])
    return response
