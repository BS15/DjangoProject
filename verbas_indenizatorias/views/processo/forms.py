from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render

from fluxo.models import Processo
from .helpers import (
    _instanciar_formularios_processo_verbas,
    _montar_contexto_processo_verbas,
    _salvar_formularios_processo_verbas,
)


@permission_required("verbas_indenizatorias.pode_gerenciar_processos_verbas", raise_exception=True)
def editar_processo_verbas(request, pk):
    processo = get_object_or_404(Processo, id=pk)
    processo_form, pendencia_formset = _instanciar_formularios_processo_verbas(request, processo)

    if request.method == 'POST':
        processo_atualizado = _salvar_formularios_processo_verbas(
            request,
            processo_form=processo_form,
            pendencia_formset=pendencia_formset,
        )
        if processo_atualizado:
            return redirect('editar_processo_verbas', pk=processo_atualizado.id)

    context = _montar_contexto_processo_verbas(
        processo,
        processo_form=processo_form,
        pendencia_formset=pendencia_formset,
    )
    return render(request, 'verbas/editar_processo_verbas.html', context)
