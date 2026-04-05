from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render

from ...filters import ReembolsoFilter
from ...forms import ReembolsoForm
from ...models import DocumentoReembolso, ReembolsoCombustivel
from .verbas_shared import (
    _anexar_documento,
    _get_tipos_documento_ativos,
    _processar_upload_documento,
    _render_lista_verba,
)


@permission_required("processos.pode_visualizar_verbas", raise_exception=True)
def reembolsos_list_view(request):
    return _render_lista_verba(request, ReembolsoCombustivel, ReembolsoFilter, 'verbas/reembolsos_list.html')


@permission_required("processos.pode_gerenciar_reembolsos", raise_exception=True)
def add_reembolso_view(request):
    if request.method == 'POST':
        form = ReembolsoForm(request.POST)
        if form.is_valid():
            novo_reembolso = form.save()
            arquivo = request.FILES.get('documento_anexo')
            tipo_id = request.POST.get('tipo_documento_anexo')
            if arquivo and tipo_id:
                _anexar_documento(DocumentoReembolso, 'reembolso', novo_reembolso, arquivo, tipo_id)
            messages.success(request, 'Reembolso cadastrado com sucesso!')
            return redirect('reembolsos_list')
    else:
        form = ReembolsoForm()

    tipos_doc = _get_tipos_documento_ativos()
    return render(request, 'verbas/add_reembolso.html', {'form': form, 'tipos_documento': tipos_doc})


@permission_required("processos.pode_gerenciar_reembolsos", raise_exception=True)
def edit_reembolso_view(request, pk):
    reembolso = get_object_or_404(ReembolsoCombustivel, id=pk)
    documentos = reembolso.documentos.select_related('tipo').all()
    tipos_doc = _get_tipos_documento_ativos()

    if request.method == 'POST':
        if request.POST.get('upload_doc'):
            _processar_upload_documento(request, reembolso, DocumentoReembolso, 'reembolso')
            return redirect('edit_reembolso', pk=reembolso.id)

        form = ReembolsoForm(request.POST, instance=reembolso)
        if form.is_valid():
            form.save()
            messages.success(request, 'Reembolso atualizado com sucesso!')
            return redirect('edit_reembolso', pk=reembolso.id)

        messages.error(request, 'Erro ao salvar. Verifique os campos.')
    else:
        form = ReembolsoForm(instance=reembolso)

    context = {
        'reembolso': reembolso,
        'form': form,
        'documentos': documentos,
        'tipos_documento': tipos_doc,
    }
    return render(request, 'verbas/edit_reembolso.html', context)
