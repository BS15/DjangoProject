"""Views de cadastro e API auxiliar para dados de credor."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from credores.filters import CredorFilter
from credores.forms import CredorForm
from credores.models import Credor
from pagamentos.views.shared import render_filtered_list


@permission_required("pagamentos.acesso_backoffice", raise_exception=True)
def add_credor_view(request):
    """Cria um novo credor a partir do formulário de cadastro."""
    if request.method == 'POST':
        form = CredorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Credor cadastrado com sucesso!")
            return redirect('home_page')
        else:
            messages.error(request, "Erro ao cadastrar. Verifique os campos.")
    else:
        form = CredorForm()

    return render(request, 'cadastros/add_credor.html', {'form': form})


@permission_required("pagamentos.acesso_backoffice", raise_exception=True)
def edit_credor_view(request, pk):
    """Edita um credor existente identificado pela chave primária."""
    credor = get_object_or_404(Credor, pk=pk)
    if request.method == 'POST':
        form = CredorForm(request.POST, instance=credor)
        if form.is_valid():
            form.save()
            messages.success(request, "Credor atualizado com sucesso!")
            return redirect('credores_list')
        else:
            messages.error(request, "Erro ao atualizar. Verifique os campos.")
    else:
        form = CredorForm(instance=credor)

    return render(request, 'cadastros/edit_credor.html', {'form': form, 'credor': credor})


@permission_required("pagamentos.acesso_backoffice", raise_exception=True)
def credores_list_view(request):
    """Lista credores com suporte a filtros do ``CredorFilter``."""
    queryset = Credor.objects.all().order_by('nome')
    return render_filtered_list(
        request,
        queryset=queryset,
        filter_class=CredorFilter,
        template_name='cadastros/credores_list.html',
        items_key='credores',
        filter_key='filter',
    )


@permission_required("pagamentos.acesso_backoffice", raise_exception=True)
def api_dados_credor(request, credor_id):
    """Retorna em JSON dados de credor para autofill em formulários."""
    try:
        # select_related otimiza a busca para já trazer a conta junto com o credor
        credor = Credor.objects.select_related('conta').get(id=credor_id)

        dados = {
            'sucesso': True,
            'cpf_cnpj': credor.cpf_cnpj,
            'pix': credor.chave_pix,
        }

        # Se o credor tiver uma conta, enviamos o ID para fazer o Autofill no HTML!
        if credor.conta:
            dados.update({
                'conta_id': credor.conta.id,
                'banco': credor.conta.banco,
                'agencia': credor.conta.agencia,
                'conta': credor.conta.conta
            })

        return JsonResponse(dados)
    except Credor.DoesNotExist:
        return JsonResponse({'sucesso': False, 'erro': 'Credor não encontrado'})
