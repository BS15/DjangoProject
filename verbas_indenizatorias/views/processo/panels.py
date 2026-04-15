from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render

from fluxo.domain_models import Processo
from fluxo.forms import PendenciaFormSet, ProcessoForm
from .helpers import _montar_contexto_processo_verbas


@permission_required("verbas_indenizatorias.pode_visualizar_verbas", raise_exception=True)
def verbas_panel_view(request):
    return render(request, 'verbas/verbas_panel.html')


@permission_required("verbas_indenizatorias.pode_gerenciar_processos_verbas", raise_exception=True)
def editar_processo_verbas_view(request, pk):
    processo = get_object_or_404(Processo, id=pk)
    processo_form = ProcessoForm(instance=processo, prefix='processo')
    pendencia_formset = PendenciaFormSet(instance=processo, prefix='pendencia')
    context = _montar_contexto_processo_verbas(
        processo,
        processo_form=processo_form,
        pendencia_formset=pendencia_formset,
    )
    return render(request, 'verbas/editar_processo_verbas.html', context)
