from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render

from ...filters import AuxilioFilter
from ...forms import AuxilioForm
from ...models import AuxilioRepresentacao, DocumentoAuxilio
from .verbas_shared import (
    _anexar_documento,
    _get_tipos_documento_ativos,
    _processar_upload_documento,
    _render_lista_verba,
)


@permission_required("processos.pode_visualizar_verbas", raise_exception=True)
def auxilios_list_view(request):
    return _render_lista_verba(request, AuxilioRepresentacao, AuxilioFilter, 'verbas/auxilios_list.html')


@permission_required("processos.pode_gerenciar_auxilios", raise_exception=True)
def add_auxilio_view(request):
    if request.method == 'POST':
        form = AuxilioForm(request.POST)
        if form.is_valid():
            novo_auxilio = form.save()
            arquivo = request.FILES.get('documento_anexo')
            tipo_id = request.POST.get('tipo_documento_anexo')
            if arquivo and tipo_id:
                _anexar_documento(DocumentoAuxilio, 'auxilio', novo_auxilio, arquivo, tipo_id)
            messages.success(request, 'Auxílio cadastrado com sucesso!')
            return redirect('auxilios_list')
    else:
        form = AuxilioForm()

    tipos_doc = _get_tipos_documento_ativos()
    return render(request, 'verbas/add_auxilio.html', {'form': form, 'tipos_documento': tipos_doc})


@permission_required("processos.pode_gerenciar_auxilios", raise_exception=True)
def edit_auxilio_view(request, pk):
    auxilio = get_object_or_404(AuxilioRepresentacao, id=pk)
    documentos = auxilio.documentos.select_related('tipo').all()
    tipos_doc = _get_tipos_documento_ativos()

    if request.method == 'POST':
        if request.POST.get('upload_doc'):
            _processar_upload_documento(request, auxilio, DocumentoAuxilio, 'auxilio')
            return redirect('edit_auxilio', pk=auxilio.id)

        form = AuxilioForm(request.POST, instance=auxilio)
        if form.is_valid():
            form.save()
            messages.success(request, 'Auxílio atualizado com sucesso!')
            return redirect('edit_auxilio', pk=auxilio.id)

        messages.error(request, 'Erro ao salvar. Verifique os campos.')
    else:
        form = AuxilioForm(instance=auxilio)

    context = {
        'auxilio': auxilio,
        'form': form,
        'documentos': documentos,
        'tipos_documento': tipos_doc,
    }
    return render(request, 'verbas/edit_auxilio.html', context)
