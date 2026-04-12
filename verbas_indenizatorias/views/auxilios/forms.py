from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render

from verbas_indenizatorias.forms import AuxilioForm
from verbas_indenizatorias.models import AuxilioRepresentacao, DocumentoAuxilio
from ..shared.documents import (
    _processar_edicao_verba_com_upload,
    _salvar_verba_com_anexo_opcional,
)
from ..shared.registry import (
    _get_tipos_documento_ativos,
)


@permission_required("fluxo.pode_gerenciar_auxilios", raise_exception=True)
def add_auxilio_view(request):
    if request.method == 'POST':
        form = AuxilioForm(request.POST)
        if form.is_valid():
            auxilio = _salvar_verba_com_anexo_opcional(
                request,
                form=form,
                modelo_documento=DocumentoAuxilio,
                fk_name='auxilio',
            )
            if auxilio:
                messages.success(request, 'Auxilio cadastrado com sucesso!')
                return redirect('auxilios_list')
        else:
            messages.error(request, 'Erro ao salvar. Verifique os campos.')
    else:
        form = AuxilioForm()

    tipos_doc = _get_tipos_documento_ativos()
    return render(request, 'verbas/add_auxilio.html', {'form': form, 'tipos_documento': tipos_doc})


@permission_required("fluxo.pode_gerenciar_auxilios", raise_exception=True)
def edit_auxilio_view(request, pk):
    auxilio = get_object_or_404(AuxilioRepresentacao, id=pk)
    documentos = auxilio.documentos.select_related('tipo').all()
    tipos_doc = _get_tipos_documento_ativos()

    form, should_redirect = _processar_edicao_verba_com_upload(
        request,
        instancia=auxilio,
        form_class=AuxilioForm,
        modelo_documento=DocumentoAuxilio,
        fk_name='auxilio',
        success_message='Auxilio atualizado com sucesso!',
    )
    if should_redirect:
        return redirect('edit_auxilio', pk=auxilio.id)

    context = {
        'auxilio': auxilio,
        'form': form,
        'documentos': documentos,
        'tipos_documento': tipos_doc,
    }
    return render(request, 'verbas/edit_auxilio.html', context)
