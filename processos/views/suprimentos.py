from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from ..forms import SuprimentoForm
from ..models import SuprimentoDeFundos, DespesaSuprimento, StatusChoicesProcesso, StatusChoicesSuprimentoDeFundos
from ..models.fluxo import Processo, FormasDePagamento, TiposDePagamento


def painel_suprimentos_view(request):
    suprimentos = SuprimentoDeFundos.objects.all().order_by('-id')
    return render(request, 'suprimentos/suprimentos_list.html', {'suprimentos': suprimentos})


def gerenciar_suprimento_view(request, pk):
    suprimento = get_object_or_404(SuprimentoDeFundos, id=pk)
    despesas = suprimento.despesas.all().order_by('data', 'id')

    is_encerrado = suprimento.status and suprimento.status.status_choice.upper() == 'ENCERRADO'
    pode_editar = not is_encerrado

    if request.method == 'POST':
        if not pode_editar:
            messages.error(request, "Este suprimento já foi encerrado e não pode receber novas despesas.")
            return redirect('gerenciar_suprimento', pk=suprimento.id)

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
        'despesas': despesas,
        'pode_editar': pode_editar,
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

        status_encerrado, _ = StatusChoicesSuprimentoDeFundos.objects.get_or_create(
            status_choice='ENCERRADO'
        )
        suprimento.status = status_encerrado
        suprimento.save(update_fields=['status'])

        messages.success(request, f'Prestação de contas do suprimento #{suprimento.id} encerrada e enviada para Conferência!')
        return redirect('painel_suprimentos')


def add_suprimento_view(request):
    if request.method == 'POST':
        form = SuprimentoForm(request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    suprimento = form.save(commit=False)

                    # Assign the mandatory Suprimento status before saving
                    status_aberto, _ = StatusChoicesSuprimentoDeFundos.objects.get_or_create(
                        status_choice='ABERTO',
                    )
                    suprimento.status = status_aberto

                    suprimento.save()

                    # Determine administrative defaults for the linked Processo
                    nome_delegacia = suprimento.lotacao or 'Unidade Não Especificada'
                    mes = suprimento.data_saida.month
                    ano = suprimento.data_saida.year
                    detalhamento = (
                        f"Referente a suprimento de fundos da {nome_delegacia} - mês {mes}/{ano}"
                    )

                    forma_pgto, _ = FormasDePagamento.objects.get_or_create(
                        forma_de_pagamento__iexact='CARTÃO PRÉ-PAGO',
                        defaults={'forma_de_pagamento': 'CARTÃO PRÉ-PAGO'},
                    )
                    tipo_pgto, _ = TiposDePagamento.objects.get_or_create(
                        tipo_de_pagamento__iexact='SUPRIMENTO DE FUNDOS',
                        defaults={'tipo_de_pagamento': 'SUPRIMENTO DE FUNDOS'},
                    )
                    status_inicial, _ = StatusChoicesProcesso.objects.get_or_create(
                        status_choice__iexact='A EMPENHAR',
                        defaults={'status_choice': 'A EMPENHAR'},
                    )

                    valor_bruto = suprimento.valor_liquido
                    valor_liquido = suprimento.valor_liquido - suprimento.taxa_saque

                    processo = Processo.objects.create(
                        credor=suprimento.suprido,
                        valor_bruto=valor_bruto,
                        valor_liquido=valor_liquido,
                        forma_pagamento=forma_pgto,
                        tipo_pagamento=tipo_pgto,
                        status=status_inicial,
                        detalhamento=detalhamento,
                        extraorcamentario=False,
                    )

                    suprimento.processo = processo
                    suprimento.save(update_fields=['processo'])

                messages.success(request, 'Suprimento de Fundos cadastrado com sucesso!')
                return redirect('painel_suprimentos')
            except Exception as e:
                messages.error(request, f'Erro ao salvar: {e}')
        else:
            messages.error(request, 'Verifique os erros no formulário.')
    else:
        form = SuprimentoForm()

    return render(request, 'suprimentos/add_suprimento.html', {'form': form})
