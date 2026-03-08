import os
from datetime import date
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count
from .forms import ProcessoForm, DocumentoFormSet, NotaFiscalFormSet, RetencaoFormSet, CredorForm, DiariaForm, ReembolsoForm, JetonForm, AuxilioForm
from .utils import extract_siscac_data, mesclar_pdfs_em_memoria, processar_pdf_boleto
from .models import Processo, NotaFiscal, StatusChoicesProcesso, Credor, Diaria, ReembolsoCombustivel, Jeton, AuxilioRepresentacao, TiposDeDocumento, DocumentoProcesso, DocumentoDiaria, DocumentoReembolso, DocumentoJeton, DocumentoAuxilio, CodigosImposto, RetencaoImposto
from .filters import ProcessoFilter, CredorFilter,DiariaFilter, ReembolsoFilter, JetonFilter, AuxilioFilter, RetencaoProcessoFilter, RetencaoNotaFilter, RetencaoIndividualFilter

def home_page(request):
    # 1. Pega todos os processos
    processos_base = Processo.objects.all().order_by('-id')

    # 2. Passa os processos e o que o usuário digitou na URL para o Filtro
    meu_filtro = ProcessoFilter(request.GET, queryset=processos_base)

    # 3. O resultado filtrado
    processos_filtrados = meu_filtro.qs

    # 4. Contexto unificado que vai para o HTML
    context = {
        'lista_processos': processos_filtrados,
        'meu_filtro': meu_filtro,
        # Pode colocar os seus cálculos de KPI_total aqui embaixo depois
    }

    return render(request, 'home.html', context)

def add_process_view(request):
    initial_data = {}
    siscac_temp_path = None

    if request.method == 'POST':
        #Handles what happens when user uses the siscac upload file
        if 'btn_extract' in request.POST and request.FILES.get('siscac_file'):
            siscac_file = request.FILES['siscac_file']
            #Tries to extract data from the file
            try:
                extracted_data = extract_siscac_data(siscac_file)
                initial_data = extracted_data
            except Exception as e:
                print(f"Erro na extração: {e}")
            #Saves the file temporarily
            path = default_storage.save(f"temp/{siscac_file.name}", ContentFile(siscac_file.read()))
            request.session['temp_siscac_path'] = path
            request.session['temp_siscac_name'] = siscac_file.name

            #Sets the form with the initial data extracted from siscac pdf
            processo_form = ProcessoForm(initial=initial_data, prefix='processo')
            nota_fiscal_formset = NotaFiscalFormSet(prefix='nota_fiscal')
            retencao_formset = RetencaoFormSet(request.POST, request.FILES, prefix='imposto')
            documento_formset = DocumentoFormSet(prefix='documento')

            #Sends the loaded form back to user
            return render(request, 'add_process.html', {
                'processo_form': processo_form,
                'nota_fiscal_formset': nota_fiscal_formset,
                'retencao_formset': retencao_formset,
                'documento_formset': documento_formset,
                'extracted_msg': "Dados extraídos! O arquivo SISCAC será anexado automaticamente ao salvar."
            })

        #Handles when user presses save button
        else:
            print("\n--- RAIO-X DO POST ---")
            print(request.POST)
            print("----------------------\n")
            # 1. Carrega apenas o formulário principal primeiro
            processo_form = ProcessoForm(request.POST, prefix='processo')

            # Se for válido, tentamos salvar tudo
            if processo_form.is_valid():
                try:
                    with transaction.atomic():
                        # A. Salva o Processo
                        processo = processo_form.save()

                        # B. Instancia os FormSets JÁ vinculados ao processo recém-criado
                        nota_fiscal_formset = NotaFiscalFormSet(request.POST, instance=processo, prefix='nota_fiscal')
                        documento_formset = DocumentoFormSet(request.POST, request.FILES, instance=processo,
                                                             prefix='documento')

                        # C. Valida os filhos (Notas e Documentos)
                        if nota_fiscal_formset.is_valid() and documento_formset.is_valid():
                            notas = nota_fiscal_formset.save()
                            documento_formset.save()  # Faltava salvar os documentos!

                            # D. Salva os impostos (Recuperando daquela lógica customizada do JS)
                            for index, nota in enumerate(notas):
                                codigos = request.POST.getlist(f'imposto_{index}_code')
                                rendimentos = request.POST.getlist(
                                    f'imposto_{index}_rendimento')  # <- Captura o novo campo
                                valores = request.POST.getlist(f'imposto_{index}_value')

                                # Usamos o zip para iterar as 3 listas ao mesmo tempo
                                for c, r, v in zip(codigos, rendimentos, valores):
                                    if c and v:  # Código e Valor Retido continuam sendo obrigatórios
                                        RetencaoImposto.objects.create(
                                            nota_fiscal=nota,
                                            codigo_id=c,
                                            # Se vier vazio, salva como nulo. Se vier preenchido, converte para float
                                            rendimento_tributavel=float(r.replace(',', '.')) if r.strip() else None,
                                            valor=float(v.replace(',', '.'))
                                        )

                            status_padrao, created = StatusChoicesProcesso.objects.get_or_create(
                                status_choice__iexact='A PAGAR',
                                defaults={'nome': 'A PAGAR'}
                            )

                            # 3. Injeta o status no processo e finalmente salva no banco
                            processo.status = status_padrao
                            processo.save()
                            # Se tudo deu certo, vai para a Home
                            return redirect('home_page')
                        else:
                            # Se as notas ou docs estiverem inválidos, imprimimos para você ver e cancelamos
                            print("❌ Erros nas Notas Fiscais:", nota_fiscal_formset.errors)
                            print("❌ Erros nos Documentos:", documento_formset.errors)
                            raise Exception("Formulários secundários inválidos.")

                except Exception as e:
                    # NUNCA USE 'pass'. O print abaixo vai te salvar horas de dor de cabeça.
                    print(f"🛑 Erro CRÍTICO ao salvar no banco: {e}")
            else:
                # SE O SISTEMA APENAS RECARREGOU A PÁGINA, O ERRO APARECERÁ AQUI NO CONSOLE
                print("❌ O Processo não salvou porque faltam dados:", processo_form.errors)

            # Se falhou e chegou aqui, re-instancia os forms para não quebrar a tela ao recarregar
            nota_fiscal_formset = NotaFiscalFormSet(request.POST, prefix='nota_fiscal')
            documento_formset = DocumentoFormSet(request.POST, request.FILES, prefix='documento')
            retencao_formset = RetencaoFormSet(prefix='imposto')  # Apenas para o HTML não dar erro de management_form

            return render(request, 'add_process.html', {
                'processo_form': processo_form,
                'nota_fiscal_formset': nota_fiscal_formset,
                'documento_formset': documento_formset,
                'retencao_formset': retencao_formset
            })
    #Handles what happens when request is get: loads process form and document form for user to fill.
    #This happens as soon as user accesses the page, because then a request is sent with method "get".
    else:
        #This sets the prefixes for the forms. Because of this, the forms inputs will be prefixed respectively according to their "group",
        #if they're from the processo form they'll be identified as such, nf, imposto, so on.
        processo_form = ProcessoForm(prefix='processo')
        nota_fiscal_formset = NotaFiscalFormSet(prefix='nota_fiscal')
        retencao_formset = RetencaoFormSet(prefix='imposto')
        documento_formset = DocumentoFormSet(prefix='documento')

        return render(request, 'add_process.html', {
            'processo_form': processo_form,
            'nota_fiscal_formset': nota_fiscal_formset,
            'retencao_formset': retencao_formset,
            'documento_formset': documento_formset
        })

def visualizar_pdf_processo(request, processo_id):
    # 1. Busca o processo no banco
    processo = get_object_or_404(Processo, id=processo_id)

    # 2. Puxa os documentos já ordenados matematicamente pela coluna 'ordem'
    documentos = processo.documentos.all().order_by('ordem')

    # 3. Filtra apenas os caminhos reais de arquivos que existem no disco
    lista_caminhos = []
    for doc in documentos:
        if doc.arquivo and os.path.exists(doc.arquivo.path):
            lista_caminhos.append(doc.arquivo.path)

    # Se não houver nenhum arquivo válido, avisa o usuário
    if not lista_caminhos:
        return HttpResponse("Este processo ainda não possui documentos em PDF anexados.", status=404)

    # 4. Envia para a "fábrica" no utils.py que resolve a fusão na memória RAM
    pdf_buffer = mesclar_pdfs_em_memoria(lista_caminhos)

    if pdf_buffer:
        # 5. Empacota o resultado e diz ao navegador: "Isto é um PDF, abra na tela!"
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        nome_arquivo = f"Processo_{processo.n_nota_empenho or processo.id}.pdf"

        # O parâmetro 'inline' faz o PDF abrir no próprio navegador em vez de forçar o download
        response['Content-Disposition'] = f'inline; filename="{nome_arquivo}"'

        return response
    else:
        # Se a ferramenta do utils.py falhar e retornar None
        return HttpResponse("Erro interno ao mesclar os PDFs.", status=500)


def editar_processo(request, pk):
    processo = get_object_or_404(Processo, id=pk)

    if request.method == 'POST':
        # 1. Carrega os formulários com os dados enviados pelo usuário E a instância do banco
        processo_form = ProcessoForm(request.POST, instance=processo, prefix='processo')
        nota_fiscal_formset = NotaFiscalFormSet(request.POST, instance=processo, prefix='nota_fiscal')
        documento_formset = DocumentoFormSet(request.POST, request.FILES, instance=processo, prefix='documento')
        retencao_formset = RetencaoFormSet(request.POST, prefix='imposto')

        if processo_form.is_valid() and nota_fiscal_formset.is_valid() and documento_formset.is_valid():
            try:
                with transaction.atomic():
                    # A. Salva o Processo atualizado
                    processo = processo_form.save()

                    # B. Salva as Notas e Documentos atualizados (o Django lida com edições e exclusões automaticamente)
                    notas = nota_fiscal_formset.save()
                    documento_formset.save()

                    # C. Atualiza os impostos (Lógica customizada do seu JS)
                    for index, nota in enumerate(nota_fiscal_formset.queryset):
                        codigos = request.POST.getlist(f'imposto_{index}_code')
                        valores = request.POST.getlist(f'imposto_{index}_value')
                        rendimentos = request.POST.getlist(f'imposto_{index}_rendimento')  # <- Captura o novo campo
                        # Limpa os impostos antigos dessa nota para recriar os novos atualizados da tela
                        nota.retencoes.all().delete()

                        for c, r, v in zip(codigos, rendimentos, valores):
                            if c and v:  # Código e Valor Retido continuam sendo obrigatórios
                                RetencaoImposto.objects.create(
                                    nota_fiscal=nota,
                                    codigo_id=c,
                                    # Se vier vazio, salva como nulo. Se vier preenchido, converte para float
                                    rendimento_tributavel=float(r.replace(',', '.')) if r.strip() else None,
                                    valor=float(v.replace(',', '.'))
                                )

                    messages.success(request, f'Processo #{processo.id} atualizado com sucesso!')
                    return redirect('home_page')

            except Exception as e:
                print(f"🛑 Erro ao atualizar no banco: {e}")
                messages.error(request, 'Erro interno ao salvar as alterações.')
        else:
            print("❌ Erros de validação:", processo_form.errors, nota_fiscal_formset.errors, documento_formset.errors)
            messages.error(request, 'Verifique os erros no formulário.')

    else:
        # 2. Carrega a página (GET) preenchendo os forms com os dados do banco
        processo_form = ProcessoForm(instance=processo, prefix='processo')
        nota_fiscal_formset = NotaFiscalFormSet(instance=processo, prefix='nota_fiscal')
        documento_formset = DocumentoFormSet(instance=processo, prefix='documento')
        retencao_formset = RetencaoFormSet(prefix='imposto')

    context = {
        'processo_form': processo_form,
        'nota_fiscal_formset': nota_fiscal_formset,
        'documento_formset': documento_formset,
        'retencao_formset': retencao_formset,
        'processo': processo
    }

    return render(request, 'editar_processo.html', context)


def painel_impostos(request):
    # Pega a visão escolhida (padrão é processos)
    visao = request.GET.get('visao', 'processos')

    # Captura todos os filtros possíveis da URL (se não existirem, ficam vazios)
    mes_filtro = request.GET.get('mes', '')
    ano_filtro = request.GET.get('ano', '')
    processo_filtro = request.GET.get('processo_id', '')
    credor_filtro = request.GET.get('credor', '')
    imposto_filtro = request.GET.get('imposto', '')

    if visao == 'processos':
        # 1. Traz todos os Processos que têm retenção
        qs = Processo.objects.filter(notas_fiscais__retencoes__isnull=False).distinct()

        # 2. Aplica os filtros apenas se o usuário tiver digitado algo
        if mes_filtro: qs = qs.filter(notas_fiscais__data_emissao__month=int(mes_filtro))
        if ano_filtro: qs = qs.filter(notas_fiscais__data_emissao__year=int(ano_filtro))
        if processo_filtro: qs = qs.filter(id=processo_filtro)
        if credor_filtro: qs = qs.filter(credor__icontains=credor_filtro)
        if imposto_filtro: qs = qs.filter(notas_fiscais__retencoes__codigo_id=imposto_filtro)

        itens = qs.prefetch_related('notas_fiscais__retencoes__codigo')

    else:
        # 1. Traz todas as Notas que têm retenção
        qs = NotaFiscal.objects.filter(retencoes__isnull=False).distinct()

        # 2. Aplica os filtros na visão de Notas
        if mes_filtro: qs = qs.filter(data_emissao__month=int(mes_filtro))
        if ano_filtro: qs = qs.filter(data_emissao__year=int(ano_filtro))
        if processo_filtro: qs = qs.filter(processo__id=processo_filtro)
        if credor_filtro: qs = qs.filter(nome_emitente__icontains=credor_filtro)
        if imposto_filtro: qs = qs.filter(retencoes__codigo_id=imposto_filtro)

        itens = qs.prefetch_related('retencoes__codigo', 'processo')

    # Busca os códigos de imposto cadastrados para montar o dropdown no HTML
    codigos_ativos = CodigosImposto.objects.filter(is_active=True)

    context = {
        'visao': visao,
        'itens': itens,
        'mes_selecionado': mes_filtro,
        'ano_selecionado': ano_filtro,
        'processo_selecionado': processo_filtro,
        'credor_selecionado': credor_filtro,
        'imposto_selecionado': imposto_filtro,
        'lista_meses': range(1, 13),
        'lista_anos': range(2024, 2030),
        'codigos_imposto': codigos_ativos,
    }

    return render(request, 'painel_impostos.html', context)

def contas_a_pagar(request):
    # 1. Filtra os processos (Ajuste o 'nome__icontains' para o nome exato do seu status no banco)
    processos_pendentes = Processo.objects.filter(status__status_choice__iexact='A PAGAR')

    # 2. Agrupa as datas únicas e conta quantos processos existem em cada data
    # Isso gera algo como: [{'data_pagamento': '2026-02-01', 'total': 5}, ...]
    datas_agrupadas = processos_pendentes.values('data_pagamento').annotate(
        total=Count('id')
    ).order_by('data_pagamento')

    # 3. Pega a data que o usuário clicou na barra lateral (se houver)
    data_selecionada = request.GET.get('data')

    # 4. Filtra a tabela principal baseada no clique
    if data_selecionada:
        if data_selecionada == 'sem_data':
            lista_processos = processos_pendentes.filter(data_pagamento__isnull=True)
        else:
            lista_processos = processos_pendentes.filter(data_pagamento=data_selecionada)
    else:
        # Se não clicou em nada, mostra todos os pendentes
        lista_processos = processos_pendentes

    context = {
        'datas_agrupadas': datas_agrupadas,
        'lista_processos': lista_processos,
        'data_selecionada': data_selecionada,
    }

    return render(request, 'contas_a_pagar.html', context)

def api_processar_boleto(request):
    """View API apenas para roteamento e resposta HTTP."""
    if request.method == 'POST' and request.FILES.get('boleto_pdf'):
        pdf_file = request.FILES['boleto_pdf']

        try:
            # Chama a lógica encapsulada
            dados = processar_pdf_boleto(pdf_file)
            return JsonResponse({'sucesso': True, 'dados': dados})

        except Exception as e:
            # Captura tanto o erro de leitura do PyPDF2 quanto o ValueError que criamos
            return JsonResponse({'sucesso': False, 'erro': str(e)})

    return JsonResponse({'sucesso': False, 'erro': 'Arquivo inválido ou não enviado.'})


def add_pre_empenho_view(request):
    if request.method == 'POST':
        processo_form = ProcessoForm(request.POST)
        # Instancie seus formsets passando o request.POST e request.FILES
        # ex: nota_fiscal_formset = NotaFiscalFormSet(request.POST, prefix='nota_fiscal')
        #     documento_formset = DocumentoFormSet(request.POST, request.FILES, prefix='documento')
        #     retencao_formset = RetencaoFormSet(request.POST, prefix='retencao')

        if processo_form.is_valid():  # e os formsets também forem válidos
            try:
                with transaction.atomic():
                    # 1. Pausa o salvamento
                    processo = processo_form.save(commit=False)

                    # 2. Busca ou cria o Status 'A EMPENHAR'
                    status_pre_empenho, created = StatusChoicesProcesso.objects.get_or_create(
                        nome__iexact='A EMPENHAR',
                        defaults={'nome': 'A EMPENHAR'}
                    )

                    # 3. Força o status e salva o processo
                    processo.status = status_pre_empenho
                    processo.save()

                    # 4. Salva os formsets vinculando ao processo recém criado
                    # ex: nota_fiscal_formset.instance = processo
                    #     nota_fiscal_formset.save()
                    #     documento_formset.instance = processo
                    #     documento_formset.save()

                    messages.success(request, "Processo salvo com sucesso na fase de Pré-Empenho!")
                    return redirect('home_page')  # Ou a rota que preferir

            except Exception as e:
                messages.error(request, f"Erro ao salvar: {e}")
        else:
            messages.error(request, "Verifique os erros no formulário.")

    else:
        processo_form = ProcessoForm()
        # Instancie os formsets vazios aqui para o GET

    context = {
        'processo_form': processo_form,
        # 'nota_fiscal_formset': nota_fiscal_formset,
        # 'documento_formset': documento_formset,
        # 'retencao_formset': retencao_formset,
    }

    return render(request, 'add_pre_empenho.html', context)

def a_empenhar_view(request):
    """Filtra e exibe apenas os processos na fila de empenho."""
    # O iexact ignora maiúsculas e minúsculas na busca
    processos_pendentes = Processo.objects.filter(
        status__nome__iexact='A EMPENHAR'
    ).order_by('data_vencimento', '-id') # Ordena pelos que vencem primeiro

    context = {
        'processos': processos_pendentes,
    }
    return render(request, 'a_empenhar.html', context)

def add_credor_view(request):
    if request.method == 'POST':
        form = CredorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Credor cadastrado com sucesso!")
            # Redireciona para a página inicial ou lista de credores
            return redirect('home_page')
        else:
            messages.error(request, "Erro ao cadastrar. Verifique os campos.")
    else:
        form = CredorForm()

    return render(request, 'add_credor.html', {'form': form})

def credores_list_view(request):
    # Busca todos os credores ordenados por nome alfabeticamente
    queryset = Credor.objects.all().order_by('nome')

    # Aplica o filtro baseado no que o usuário digitou na URL (GET)
    meu_filtro = CredorFilter(request.GET, queryset=queryset)

    context = {
        'filter': meu_filtro,
        'credores': meu_filtro.qs,  # .qs retorna o resultado já filtrado
    }
    return render(request, 'credores_list.html', context)
def diarias_list_view(request):
    queryset = Diaria.objects.select_related('beneficiario', 'status', 'processo').all().order_by('-id')
    meu_filtro = DiariaFilter(request.GET, queryset=queryset)
    return render(request, 'diarias_list.html', {'filter': meu_filtro, 'registros': meu_filtro.qs})

def reembolsos_list_view(request):
    queryset = ReembolsoCombustivel.objects.select_related('beneficiario', 'status', 'processo').all().order_by('-id')
    meu_filtro = ReembolsoFilter(request.GET, queryset=queryset)
    return render(request, 'reembolsos_list.html', {'filter': meu_filtro, 'registros': meu_filtro.qs})

def jetons_list_view(request):
    queryset = Jeton.objects.select_related('beneficiario', 'status', 'processo').all().order_by('-id')
    meu_filtro = JetonFilter(request.GET, queryset=queryset)
    return render(request, 'jetons_list.html', {'filter': meu_filtro, 'registros': meu_filtro.qs})

def auxilios_list_view(request):
    queryset = AuxilioRepresentacao.objects.select_related('beneficiario', 'status', 'processo').all().order_by('-id')
    meu_filtro = AuxilioFilter(request.GET, queryset=queryset)
    return render(request, 'auxilios_list.html', {'filter': meu_filtro, 'registros': meu_filtro.qs})

def add_diaria_view(request):
    if request.method == 'POST':
        form = DiariaForm(request.POST)
        if form.is_valid():
            nova_diaria = form.save()
            # Lógica do Anexo
            arquivo = request.FILES.get('documento_anexo')
            tipo_id = request.POST.get('tipo_documento_anexo')
            if arquivo and tipo_id:
                DocumentoDiaria.objects.create(diaria=nova_diaria, arquivo=arquivo, tipo_id=tipo_id)
            messages.success(request, 'Diária cadastrada com sucesso!')
            return redirect('diarias_list')
        else:
            messages.error(request, 'Erro ao salvar. Verifique os campos.')
    else:
        form = DiariaForm()

    tipos_doc = TiposDeDocumento.objects.filter(is_active=True)
    return render(request, 'add_diaria.html', {'form': form, 'tipos_documento': tipos_doc})

def add_reembolso_view(request):
    if request.method == 'POST':
        form = ReembolsoForm(request.POST)
        if form.is_valid():
            novo_reembolso = form.save()
            arquivo = request.FILES.get('documento_anexo')
            tipo_id = request.POST.get('tipo_documento_anexo')
            if arquivo and tipo_id:
                DocumentoReembolso.objects.create(reembolso=novo_reembolso, arquivo=arquivo, tipo_id=tipo_id)
            messages.success(request, 'Reembolso cadastrado com sucesso!')
            return redirect('reembolsos_list')
    else:
        form = ReembolsoForm()

    tipos_doc = TiposDeDocumento.objects.filter(is_active=True)
    return render(request, 'add_reembolso.html', {'form': form, 'tipos_documento': tipos_doc})

def add_jeton_view(request):
    if request.method == 'POST':
        form = JetonForm(request.POST)
        if form.is_valid():
            novo_jeton = form.save()
            arquivo = request.FILES.get('documento_anexo')
            tipo_id = request.POST.get('tipo_documento_anexo')
            if arquivo and tipo_id:
                DocumentoJeton.objects.create(jeton=novo_jeton, arquivo=arquivo, tipo_id=tipo_id)
            messages.success(request, 'Jeton cadastrado com sucesso!')
            return redirect('jetons_list')
    else:
        form = JetonForm()

    tipos_doc = TiposDeDocumento.objects.filter(is_active=True)
    return render(request, 'add_jeton.html', {'form': form, 'tipos_documento': tipos_doc})

def add_auxilio_view(request):
    if request.method == 'POST':
        form = AuxilioForm(request.POST)
        if form.is_valid():
            novo_auxilio = form.save()
            arquivo = request.FILES.get('documento_anexo')
            tipo_id = request.POST.get('tipo_documento_anexo')
            if arquivo and tipo_id:
                DocumentoAuxilio.objects.create(auxilio=novo_auxilio, arquivo=arquivo, tipo_id=tipo_id)
            messages.success(request, 'Auxílio cadastrado com sucesso!')
            return redirect('auxilios_list')
    else:
        form = AuxilioForm()

    tipos_doc = TiposDeDocumento.objects.filter(is_active=True)
    return render(request, 'add_auxilio.html', {'form': form, 'tipos_documento': tipos_doc})

def verbas_panel_view(request):
    """Renderiza o painel centralizador das Verbas Indenizatórias."""
    return render(request, 'verbas_panel.html')


def agrupar_verbas_view(request, tipo_verba):
    if request.method != 'POST':
        return redirect('verbas_panel')

    # Captura todos os checkboxes marcados no HTML
    selecionados = request.POST.getlist('verbas_selecionadas')

    # Dicionário explícito para saber qual Modelo e qual URL usar
    MAPA_VERBAS = {
        'diaria': (Diaria, 'diarias_list'),
        'reembolso': (ReembolsoCombustivel, 'reembolsos_list'),
        'jeton': (Jeton, 'jetons_list'),
        'auxilio': (AuxilioRepresentacao, 'auxilios_list'),
    }

    if tipo_verba not in MAPA_VERBAS:
        return redirect('verbas_panel')

    ModeloVerba, url_retorno = MAPA_VERBAS[tipo_verba]

    if not selecionados:
        messages.warning(request, "Nenhum item selecionado para agrupar.")
        return redirect(url_retorno)

    # Busca no banco APENAS os itens selecionados que AINDA NÃO têm um processo
    itens = ModeloVerba.objects.filter(id__in=selecionados, processo__isnull=True)

    if not itens.exists():
        messages.warning(request, "Os itens selecionados já possuem processo ou são inválidos.")
        return redirect(url_retorno)

    # 1. Calcula o total somando tudo
    total = sum(item.valor_total for item in itens if item.valor_total)

    # 2. Pega o nome do credor do primeiro item para preencher o processo
    credor_nome = itens.first().beneficiario.nome

    # 3. Cria o Processo "Pai"
    novo_processo = Processo.objects.create(
        credor=credor_nome,
        valor_bruto=total,
        valor_liquido=total,
        detalhamento=f"Agrupamento de {tipo_verba.capitalize()}s"
    )

    # 4. Atualiza os itens com o ID do processo e clona os documentos
    for item in itens:
        item.processo = novo_processo
        item.save()

        # Puxa os documentos específicos da verba e joga na tabela do Processo
        for doc in item.documentos.all():
            DocumentoProcesso.objects.create(
                processo=novo_processo,
                arquivo=doc.arquivo,  # Usa o mesmo arquivo físico (não duplica no HD)
                tipo=doc.tipo,
                ordem=doc.ordem
            )

    messages.success(request, f"Processo #{novo_processo.id} gerado com sucesso! Os documentos foram importados.")

    # Redireciona direto para a tela do processo criado para o usuário terminar de preencher (data, conta, etc)
    return redirect('editar_processo', pk=novo_processo.id)


def agrupar_impostos_view(request):
    if request.method != 'POST':
        return redirect('painel_impostos')

    selecionados = request.POST.getlist('itens_selecionados')
    visao = request.POST.get('visao_atual')

    if not selecionados:
        messages.warning(request, "Nenhum item selecionado para agrupar.")
        return redirect('painel_impostos')

    total_impostos = 0

    # Agora verificamos as 3 visões para puxar os impostos corretamente
    if visao == 'processos':
        retencoes = RetencaoImposto.objects.filter(nota_fiscal__processo__id__in=selecionados)
    elif visao == 'notas':
        retencoes = RetencaoImposto.objects.filter(nota_fiscal__id__in=selecionados)
    else: # visao == 'retencoes' (os IDs já são diretamente das retenções)
        retencoes = RetencaoImposto.objects.filter(id__in=selecionados)

    for retencao in retencoes:
        if retencao.valor:
            total_impostos += retencao.valor

    if total_impostos <= 0:
        messages.warning(request, "Os itens selecionados não possuem valores válidos.")
        return redirect('painel_impostos')

    novo_processo = Processo.objects.create(
        credor="Órgão Arrecadador (A Definir)",
        valor_bruto=total_impostos,
        valor_liquido=total_impostos,
        detalhamento="Pagamento Agrupado de Impostos Retidos",
        observacao="Gerado automaticamente."
    )

    messages.success(request, f"Processo #{novo_processo.id} para recolhimento gerado com sucesso!")
    return redirect('editar_processo', pk=novo_processo.id)


def painel_impostos(request):
    visao = request.GET.get('visao', 'processos')

    if visao == 'processos':
        queryset_base = Processo.objects.filter(notas_fiscais__retencoes__isnull=False).distinct()
        meu_filtro = RetencaoProcessoFilter(request.GET, queryset=queryset_base)
        itens = meu_filtro.qs.prefetch_related('notas_fiscais__retencoes__codigo', 'notas_fiscais__retencoes__status')

    elif visao == 'notas':
        queryset_base = NotaFiscal.objects.filter(retencoes__isnull=False).distinct()
        meu_filtro = RetencaoNotaFilter(request.GET, queryset=queryset_base)
        itens = meu_filtro.qs.prefetch_related('retencoes__codigo', 'retencoes__status', 'processo')

    else:
        # VISÃO 3: Retenções Individuais (carrega todas por padrão se não houver filtro)
        queryset_base = RetencaoImposto.objects.all().order_by('-id')
        meu_filtro = RetencaoIndividualFilter(request.GET, queryset=queryset_base)
        # select_related é melhor aqui pois estamos indo do item "filho" para os "pais"
        itens = meu_filtro.qs.select_related('codigo', 'status', 'nota_fiscal', 'nota_fiscal__processo')

    context = {
        'visao': visao,
        'meu_filtro': meu_filtro,
        'itens': itens,
    }

    return render(request, 'painel_impostos.html', context)


def painel_comprovantes_view(request):
    """Renderiza a tela. Passa os processos A PAGAR como um JSON para o Javascript consumir."""
    # Busca apenas processos na fila de pagamento
    processos_pendentes = Processo.objects.filter(status__status_choice__iexact='A PAGAR').values(
        'id', 'credor', 'valor_liquido', 'n_nota_empenho'
    )

    context = {
        # Converte a queryset para uma lista JSON que o Javascript consegue ler
        'processos_json': json.dumps(list(processos_pendentes), default=str)
    }
    return render(request, 'painel_comprovantes.html', context)


def api_fatiar_comprovantes(request):
    """Recebe o PDF do banco e devolve os dados extraídos."""
    if request.method == 'POST' and request.FILES.get('pdf_banco'):
        try:
            resultados = processar_pdf_comprovantes(request.FILES['pdf_banco'])
            return JsonResponse({'sucesso': True, 'comprovantes': resultados})
        except Exception as e:
            return JsonResponse({'sucesso': False, 'erro': str(e)})
    return JsonResponse({'sucesso': False, 'erro': 'Arquivo não enviado.'})


@transaction.atomic
def api_vincular_comprovantes(request):
    """Recebe as escolhas do usuário, anexa os arquivos e muda o status para PAGO."""
    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            vinculos = dados.get('vinculos', [])

            status_pago, _ = StatusChoicesProcesso.objects.get_or_create(
                status_choice__iexact='PAGO', defaults={'nome': 'PAGO'}
            )

            tipo_comprovante, _ = TiposDeDocumento.objects.get_or_create(
                tipo_de_documento__iexact='Comprovante de Pagamento',
                defaults={'tipo_de_documento': 'Comprovante de Pagamento'}
            )

            processos_atualizados = 0

            for vinculo in vinculos:
                processo_id = vinculo.get('processo_id')
                temp_path = vinculo.get('temp_path')

                if not processo_id or not temp_path:
                    continue

                processo = Processo.objects.get(id=processo_id)

                # 1. Abre o arquivo temporário fatiado
                if default_storage.exists(temp_path):
                    with default_storage.open(temp_path) as temp_file:
                        # 2. Cria o anexo no banco
                        DocumentoProcesso.objects.create(
                            processo=processo,
                            arquivo=ContentFile(temp_file.read(), name=f"Comprovante_Proc_{processo.id}.pdf"),
                            tipo=tipo_comprovante,
                            ordem=99  # Joga pro final da lista de docs
                        )

                    # Limpa o arquivo temporário
                    default_storage.delete(temp_path)

                # 3. Hard-set do status para PAGO
                processo.status = status_pago
                processo.save()
                processos_atualizados += 1

            return JsonResponse(
                {'sucesso': True, 'mensagem': f'{processos_atualizados} processos baixados com sucesso!'})

        except Exception as e:
            return JsonResponse({'sucesso': False, 'erro': str(e)})

    return JsonResponse({'sucesso': False, 'erro': 'Método inválido.'})