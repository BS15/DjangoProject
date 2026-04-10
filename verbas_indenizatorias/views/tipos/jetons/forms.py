from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render

from verbas_indenizatorias.forms import JetonForm
from verbas_indenizatorias.models import DocumentoJeton, Jeton
from ...shared.documents import (
    _processar_edicao_verba_com_upload,
    _salvar_verba_com_anexo_opcional,
)
from ...shared.registry import (
    _get_tipos_documento_ativos,
)


@permission_required("fluxo.pode_gerenciar_jetons", raise_exception=True)
def add_jeton_view(request):
    if request.method == 'POST':
        form = JetonForm(request.POST)
        if form.is_valid():
            jeton = _salvar_verba_com_anexo_opcional(
                request,
                form=form,
                modelo_documento=DocumentoJeton,
                fk_name='jeton',
            )
            if jeton:
                messages.success(request, 'Jeton cadastrado com sucesso!')
                return redirect('jetons_list')
        else:
            messages.error(request, 'Erro ao salvar. Verifique os campos.')
    else:
        form = JetonForm()

    tipos_doc = _get_tipos_documento_ativos()
    return render(request, 'verbas/add_jeton.html', {'form': form, 'tipos_documento': tipos_doc})


@permission_required("fluxo.pode_gerenciar_jetons", raise_exception=True)
def edit_jeton_view(request, pk):
    jeton = get_object_or_404(Jeton, id=pk)
    documentos = jeton.documentos.select_related('tipo').all()
    tipos_doc = _get_tipos_documento_ativos()

    form, should_redirect = _processar_edicao_verba_com_upload(
        request,
        instancia=jeton,
        form_class=JetonForm,
        modelo_documento=DocumentoJeton,
        fk_name='jeton',
        success_message='Jeton atualizado com sucesso!',
    )
    if should_redirect:
        return redirect('edit_jeton', pk=jeton.id)

    context = {
        'jeton': jeton,
        'form': form,
        'documentos': documentos,
        'tipos_documento': tipos_doc,
    }
    return render(request, 'verbas/edit_jeton.html', context)
