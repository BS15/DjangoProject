from django.contrib.auth.decorators import permission_required

from verbas_indenizatorias.models import ReembolsoCombustivel
from verbas_indenizatorias.filters import ReembolsoFilter
from ...shared.lists import _render_lista_verba


@permission_required("fluxo.pode_visualizar_verbas", raise_exception=True)
def reembolsos_list_view(request):
    return _render_lista_verba(request, ReembolsoCombustivel, ReembolsoFilter, 'verbas/reembolsos_list.html')
