from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from ..forms import SuprimentoForm
from ..models import SuprimentoDeFundos, DespesaSuprimento, StatusChoicesProcesso


def painel_suprimentos_view(request):
    suprimentos = SuprimentoDeFundos.objects.all().order_by('-id')
    return render(request, 'suprimentos/suprimentos_list.html', {'suprimentos': suprimentos})


def gerenciar_suprimento_view(request, pk):
    suprimento = get_object_or_404(SuprimentoDeFundos, id=pk)
    despesas = suprimento.despesas.all().order_by('data', 'id')

    if request.method == 'POST':
        data = request.POST.get('data')
        estabelecimento = request.POST.get('estabelecimento')
        detalhamento = request.POST.get('detalhamento')
        nota_fiscal = request.POST.get('nota_fiscal')
        valor = request.POST.get('valor').replace(',', '.')
        arquivo_pdf = request.FILES.get('arquivo')

        if data and valor and detalhamento:
            DespesaSuprimento.objects.create(
                suprimento=suprimento,
                data=data,
                estabelecimento=estabelecimento,
                detalhamento=detalhamento,
                nota_fiscal=nota_fiscal,
                valor=float(valor),
                arquivo=arquivo_pdf
            )
            messages.success(request, 'Despesa e documento anexados com sucesso!')
            return redirect('gerenciar_suprimento', pk=suprimento.id)

    context = {
        'suprimento': suprimento,
        'despesas': despesas
    }
    return render(request, 'suprimentos/gerenciar_suprimento.html', context)


def fechar_suprimento_view(request, pk):
    if request.method == 'POST':
        suprimento = get_object_or_404(SuprimentoDeFundos, id=pk)
        processo = suprimento.processo

        status_conferencia, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact='PAGO - EM CONFERÊNCIA',
            defaults={'status_choice': 'PAGO - EM CONFERÊNCIA'}
        )

        if processo:
            processo.status = status_conferencia
            processo.save()

        messages.success(request, f'Prestação de contas do suprimento #{suprimento.id} encerrada e enviada para Conferência!')
        return redirect('painel_suprimentos')


def add_suprimento_view(request):
    if request.method == 'POST':
        form = SuprimentoForm(request.POST)

        if form.is_valid():
            try:
                suprimento = form.save()
                messages.success(request, 'Suprimento de Fundos cadastrado com sucesso!')
                return redirect('painel_suprimentos')
            except Exception as e:
                messages.error(request, f'Erro ao salvar: {e}')
        else:
            messages.error(request, 'Verifique os erros no formulário.')
    else:
        form = SuprimentoForm()

    return render(request, 'suprimentos/add_suprimento.html', {'form': form})
