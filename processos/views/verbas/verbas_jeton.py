from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render

from ...filters import JetonFilter
from ...forms import JetonForm
from ...models import DocumentoJeton, Jeton
from .verbas_shared import (
    _anexar_documento,
    _get_tipos_documento_ativos,
    _processar_upload_documento,
    _render_lista_verba,
)


@permission_required("processos.pode_visualizar_verbas", raise_exception=True)
def jetons_list_view(request):
    return _render_lista_verba(request, Jeton, JetonFilter, 'verbas/jetons_list.html')


@permission_required("processos.pode_gerenciar_jetons", raise_exception=True)
def add_jeton_view(request):
    if request.method == 'POST':
        form = JetonForm(request.POST)
        if form.is_valid():
            novo_jeton = form.save()
            arquivo = request.FILES.get('documento_anexo')
            tipo_id = request.POST.get('tipo_documento_anexo')
            if arquivo and tipo_id:
                _anexar_documento(DocumentoJeton, 'jeton', novo_jeton, arquivo, tipo_id)
            messages.success(request, 'Jeton cadastrado com sucesso!')
            return redirect('jetons_list')
    else:
        form = JetonForm()

    tipos_doc = _get_tipos_documento_ativos()
    return render(request, 'verbas/add_jeton.html', {'form': form, 'tipos_documento': tipos_doc})


@permission_required("processos.pode_gerenciar_jetons", raise_exception=True)
def edit_jeton_view(request, pk):
    jeton = get_object_or_404(Jeton, id=pk)
    documentos = jeton.documentos.select_related('tipo').all()
    tipos_doc = _get_tipos_documento_ativos()

    if request.method == 'POST':
        if request.POST.get('upload_doc'):
            _processar_upload_documento(request, jeton, DocumentoJeton, 'jeton')
            return redirect('edit_jeton', pk=jeton.id)

        form = JetonForm(request.POST, instance=jeton)
        if form.is_valid():
            form.save()
            messages.success(request, 'Jeton atualizado com sucesso!')
            return redirect('edit_jeton', pk=jeton.id)

        messages.error(request, 'Erro ao salvar. Verifique os campos.')
    else:
        form = JetonForm(instance=jeton)

    context = {
        'jeton': jeton,
        'form': form,
        'documentos': documentos,
        'tipos_documento': tipos_doc,
    }
    return render(request, 'verbas/edit_jeton.html', context)
