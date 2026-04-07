from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render

from .....forms import ReembolsoForm
from .....models import DocumentoReembolso, ReembolsoCombustivel
from ...verbas_shared import (
    _get_tipos_documento_ativos,
    _processar_edicao_verba_com_upload,
    _salvar_verba_com_anexo_opcional,
)


@permission_required("processos.pode_gerenciar_reembolsos", raise_exception=True)
def add_reembolso_view(request):
    if request.method == 'POST':
        form = ReembolsoForm(request.POST)
        if form.is_valid():
            reembolso = _salvar_verba_com_anexo_opcional(
                request,
                form=form,
                modelo_documento=DocumentoReembolso,
                fk_name='reembolso',
            )
            if reembolso:
                messages.success(request, 'Reembolso cadastrado com sucesso!')
                return redirect('reembolsos_list')
        else:
            messages.error(request, 'Erro ao salvar. Verifique os campos.')
    else:
        form = ReembolsoForm()

    tipos_doc = _get_tipos_documento_ativos()
    return render(request, 'verbas/add_reembolso.html', {'form': form, 'tipos_documento': tipos_doc})


@permission_required("processos.pode_gerenciar_reembolsos", raise_exception=True)
def edit_reembolso_view(request, pk):
    reembolso = get_object_or_404(ReembolsoCombustivel, id=pk)
    documentos = reembolso.documentos.select_related('tipo').all()
    tipos_doc = _get_tipos_documento_ativos()

    form, should_redirect = _processar_edicao_verba_com_upload(
        request,
        instancia=reembolso,
        form_class=ReembolsoForm,
        modelo_documento=DocumentoReembolso,
        fk_name='reembolso',
        success_message='Reembolso atualizado com sucesso!',
    )
    if should_redirect:
        return redirect('edit_reembolso', pk=reembolso.id)

    context = {
        'reembolso': reembolso,
        'form': form,
        'documentos': documentos,
        'tipos_documento': tipos_doc,
    }
    return render(request, 'verbas/edit_reembolso.html', context)
