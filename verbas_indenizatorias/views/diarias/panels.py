from django.contrib.auth.decorators import permission_required

from verbas_indenizatorias.models import Diaria
from verbas_indenizatorias.filters import DiariaFilter
from ..shared.lists import _render_lista_verba

@permission_required("fluxo.pode_visualizar_verbas", raise_exception=True)
def diarias_list_view(request):
    return _render_lista_verba(request, Diaria, DiariaFilter, 'verbas/diarias_list.html')
