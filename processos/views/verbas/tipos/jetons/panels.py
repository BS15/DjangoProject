from django.contrib.auth.decorators import permission_required

from .....filters import JetonFilter
from .....models import Jeton
from ...verbas_shared import _render_lista_verba


@permission_required("processos.pode_visualizar_verbas", raise_exception=True)
def jetons_list_view(request):
    return _render_lista_verba(request, Jeton, JetonFilter, 'verbas/jetons_list.html')
