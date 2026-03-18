from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from ..forms import CredorForm
from ..models import Credor
from ..filters import CredorFilter


def add_credor_view(request):
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


def edit_credor_view(request, pk):
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


def credores_list_view(request):
    queryset = Credor.objects.all().order_by('nome')
    meu_filtro = CredorFilter(request.GET, queryset=queryset)

    context = {
        'filter': meu_filtro,
        'credores': meu_filtro.qs,
    }
    return render(request, 'cadastros/credores_list.html', context)


def api_dados_credor(request, credor_id):
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
