import csv

from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse
from django.shortcuts import render

from verbas_indenizatorias.models import Diaria
from verbas_indenizatorias.filters import DiariaFilter
from ...verbas_shared import _render_lista_verba


@permission_required('fluxo.pode_visualizar_verbas', raise_exception=True)
def diarias_list_view(request):
    return _render_lista_verba(request, Diaria, DiariaFilter, 'verbas/diarias_list.html')


@permission_required('fluxo.pode_importar_diarias', raise_exception=True)
def download_template_diarias_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="template_diarias.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            'NOME_BENEFICIARIO',
            'DATA_SAIDA',
            'DATA_RETORNO',
            'CIDADE_ORIGEM',
            'CIDADE_DESTINO',
            'OBJETIVO',
            'QUANTIDADE_DIARIAS',
        ]
    )
    return response


def minhas_solicitacoes_view(request):
    diarias = Diaria.objects.filter(beneficiario__email=request.user.email).order_by('-id')
    return render(request, 'verbas/minhas_solicitacoes.html', {'diarias': diarias})
