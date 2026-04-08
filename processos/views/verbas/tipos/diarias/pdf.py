from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404

from .....models import Diaria
from .....services.shared import gerar_resposta_pdf


@permission_required('processos.pode_gerenciar_diarias', raise_exception=True)
def gerar_pcd_view(request, pk):
    diaria = get_object_or_404(Diaria, pk=pk)
    nome_arquivo = f'PCD_{diaria.numero_siscac}.pdf'
    return gerar_resposta_pdf('pcd', diaria, nome_arquivo, inline=True)
