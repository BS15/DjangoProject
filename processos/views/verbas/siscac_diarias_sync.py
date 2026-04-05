"""Views de sincronização de diárias via SISCAC."""

import logging

from django.contrib import messages
from django.shortcuts import render

from ...utils import sync_diarias_siscac_csv

logger = logging.getLogger(__name__)


def sincronizar_diarias(request):
    """Sincroniza diárias via CSV SISCAC."""
    context = {}
    if request.method == 'POST' and 'siscac_csv' in request.FILES:
        csv_file = request.FILES['siscac_csv']
        try:
            resultados = sync_diarias_siscac_csv(csv_file)
            context['resultados'] = resultados
        except UnicodeDecodeError:
            messages.error(request, 'Erro de codificação: verifique se o arquivo está em UTF-8.')
        except Exception as e:
            logger.exception('Erro ao processar CSV SISCAC Diárias', exc_info=e)
            messages.error(request, 'Erro ao processar o arquivo CSV. Verifique o formato e tente novamente.')
    return render(request, 'verbas/sincronizar_diarias.html', context)


__all__ = [
    'sincronizar_diarias',
]
