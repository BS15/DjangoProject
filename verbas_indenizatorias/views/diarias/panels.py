from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from fluxo.views.shared import render_filtered_list
from verbas_indenizatorias.forms import DiariaForm
from verbas_indenizatorias.models import Diaria
from verbas_indenizatorias.filters import DiariaFilter
from .access import _pode_acessar_prestacao
from ..shared.registry import _get_tipos_documento_verbas

@permission_required("verbas_indenizatorias.pode_visualizar_verbas", raise_exception=True)
def diarias_list_view(request):
    queryset = Diaria.objects.select_related("beneficiario", "status", "processo").order_by("-id")
    return render_filtered_list(
        request,
        queryset=queryset,
        filter_class=DiariaFilter,
        template_name='verbas/diarias_list.html',
        items_key='diarias',
        filter_key='filter',
    )


@permission_required("verbas_indenizatorias.pode_criar_diarias", raise_exception=True)
def add_diaria_view(request):
    return render(request, 'verbas/add_diaria.html', {'form': DiariaForm()})


def gerenciar_diaria_view(request, pk):
    diaria = get_object_or_404(Diaria.objects.select_related('beneficiario', 'status', 'processo'), id=pk)
    if not _pode_acessar_prestacao(request.user, diaria):
        return HttpResponseForbidden("Acesso negado para prestação de contas desta diária.")

    comprovantes = diaria.documentos.select_related('tipo').all()

    context = {
        'diaria': diaria,
        'comprovantes': comprovantes,
        'tipos_documento': _get_tipos_documento_verbas(),
    }
    return render(request, 'verbas/gerenciar_diaria.html', context)


@permission_required("verbas_indenizatorias.pode_importar_diarias", raise_exception=True)
def download_template_diarias_csv(request):
    """Baixa um CSV-modelo para importação de diárias."""
    conteudo = (
        "NOME_BENEFICIARIO,DATA_SOLICITACAO,DATA_SAIDA,DATA_RETORNO,QUANTIDADE_DIARIAS,CIDADE_ORIGEM,CIDADE_DESTINO,OBJETIVO,TIPO_SOLICITACAO\n"
    )
    response = HttpResponse(conteudo, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="template_diarias.csv"'
    return response


__all__ = [
    'diarias_list_view',
    'add_diaria_view',
    'gerenciar_diaria_view',
    'download_template_diarias_csv',
]
