from django.contrib.auth.decorators import permission_required

from .....filters import ReembolsoFilter
from .....models import ReembolsoCombustivel
from ...verbas_shared import _render_lista_verba


@permission_required("processos.pode_visualizar_verbas", raise_exception=True)
def reembolsos_list_view(request):
    return _render_lista_verba(request, ReembolsoCombustivel, ReembolsoFilter, 'verbas/reembolsos_list.html')
