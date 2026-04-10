from django.contrib.auth.decorators import permission_required

from verbas_indenizatorias.models import Jeton
from verbas_indenizatorias.filters import JetonFilter
from ...verbas_shared import _render_lista_verba


@permission_required("fluxo.pode_visualizar_verbas", raise_exception=True)
def jetons_list_view(request):
    return _render_lista_verba(request, Jeton, JetonFilter, 'verbas/jetons_list.html')
