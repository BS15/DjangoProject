from django.contrib.auth.decorators import permission_required

from .....filters import AuxilioFilter
from .....models import AuxilioRepresentacao
from ...verbas_shared import _render_lista_verba


@permission_required("processos.pode_visualizar_verbas", raise_exception=True)
def auxilios_list_view(request):
    return _render_lista_verba(request, AuxilioRepresentacao, AuxilioFilter, 'verbas/auxilios_list.html')
