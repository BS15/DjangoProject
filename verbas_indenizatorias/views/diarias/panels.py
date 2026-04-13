from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse

from fluxo.views.shared import render_filtered_list
from verbas_indenizatorias.models import Diaria
from verbas_indenizatorias.filters import DiariaFilter
from ..shared.lists import _render_lista_verba

@permission_required("fluxo.pode_visualizar_verbas", raise_exception=True)
def diarias_list_view(request):
    return _render_lista_verba(request, Diaria, DiariaFilter, 'verbas/diarias_list.html')


@permission_required("fluxo.pode_importar_diarias", raise_exception=True)
def download_template_diarias_csv(request):
    """Baixa um CSV-modelo para importação de diárias."""
    conteudo = (
        "NOME_BENEFICIARIO,DATA_SAIDA,DATA_RETORNO,QUANTIDADE_DIARIAS,CIDADE_ORIGEM,CIDADE_DESTINO,OBJETIVO,TIPO_SOLICITACAO\n"
    )
    response = HttpResponse(conteudo, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="template_diarias.csv"'
    return response


@permission_required("fluxo.pode_visualizar_verbas", raise_exception=True)
def minhas_solicitacoes_view(request):
    """Lista diárias propostas pelo usuário logado."""
    queryset = Diaria.objects.filter(proponente=request.user).select_related("beneficiario", "status").order_by("-id")
    return render_filtered_list(
        request,
        queryset=queryset,
        filter_class=DiariaFilter,
        template_name='verbas/diarias_list.html',
        items_key='registros',
        filter_key='filter',
    )
