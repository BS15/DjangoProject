import os
import json
from datetime import date
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, Q, F
from .forms import ProcessoForm, DocumentoFormSet, NotaFiscalFormSet, RetencaoFormSet, CredorForm, DiariaForm,ReembolsoForm, JetonForm, AuxilioForm, SuprimentoForm
from .utils import extract_siscac_data, mesclar_pdfs_em_memoria, processar_pdf_boleto, processar_pdf_comprovantes
from .ai_utils import processar_pdf_comprovantes_ia
from .models import Processo, NotaFiscal, StatusChoicesProcesso, Credor, Diaria, ReembolsoCombustivel, Jeton, AuxilioRepresentacao, TiposDeDocumento, DocumentoProcesso, DocumentoDiaria, DocumentoReembolso, DocumentoJeton, DocumentoAuxilio, CodigosImposto, RetencaoImposto, SuprimentoDeFundos, DespesaSuprimento
from .filters import ProcessoFilter, CredorFilter, DiariaFilter, ReembolsoFilter, JetonFilter, AuxilioFilter, \
    RetencaoProcessoFilter, RetencaoNotaFilter, RetencaoIndividualFilter


def home_page(request):
    processos_base = Processo.objects.all().order_by('-id')
    meu_filtro = ProcessoFilter(request.GET, queryset=processos_base)
    processos_filtrados = meu_filtro.qs

    context = {
        'lista_processos': processos_filtrados,
        'meu_filtro': meu_filtro,
    }
    return render(request, 'home.html', context)


def add_process_view(request):
    initial_data = {}
    siscac_temp_path = None

    if request.method == 'POST':
        if 'btn_extract' in request.POST and request.FILES.get('siscac_file'):
            siscac_file = request.FILES['siscac_file']
            try:
                extracted_data = extract_siscac_data(siscac_file)
                initial_data = extracted_data
            except Exception as e:
                print(f"Erro na extração: {e}")
            path = default_storage.save(f"temp/{siscac_file.name}", ContentFile(siscac_file.read()))
            request.session['temp_siscac_path'] = path
            request.session['temp_siscac_name'] = siscac_file.name

            processo_form = ProcessoForm(initial=initial_data, prefix='processo')
            nota_fiscal_formset = NotaFiscalFormSet(prefix='nota_fiscal')
            retencao_formset = RetencaoFormSet(request.POST, request.FILES, prefix='imposto')
            documento_formset = DocumentoFormSet(prefix='documento')

            return render(request, 'add_process.html', {
                'processo_form': processo_form,
                'nota_fiscal_formset': nota_fiscal_formset,
                'retencao_formset': retencao_formset,
                'documento_formset': documento_formset,
                'extracted_msg': "Dados extraídos! O arquivo SISCAC será anexado automaticamente ao salvar."
            })

        else:
            processo_form = ProcessoForm(request.POST, prefix='processo')

            if processo_form.is_valid():
                try:
                    with transaction.atomic():
                        processo = processo_form.save()

                        nota_fiscal_formset = NotaFiscalFormSet(request.POST, instance=processo, prefix='nota_fiscal')
                        documento_formset = DocumentoFormSet(request.POST, request.FILES, instance=processo,
                                                             prefix='documento')

                        if nota_fiscal_formset.is_valid() and documento_formset.is_valid():
                            notas = nota_fiscal_formset.save()
                            documento_formset.save()

                            for index, nota in enumerate(notas):
                                codigos = request.POST.getlist(f'imposto_{index}_code')
                                rendimentos = request.POST.getlist(f'imposto_{index}_rendimento')
                                valores = request.POST.getlist(f'imposto_{index}_value')

                                for c, r, v in zip(codigos, rendimentos, valores):
                                    if c and v:
                                        RetencaoImposto.objects.create(
                                            nota_fiscal=nota,
                                            codigo_id=c,
                                            rendimento_tributavel=float(r.replace(',', '.')) if r.strip() else None,
                                            valor=float(v.replace(',', '.'))
                                        )

                            # --- STATUS ATUALIZADO ---
                            status_padrao, created = StatusChoicesProcesso.objects.get_or_create(
                                status_choice__iexact='A PAGAR - AGUARDANDO AUTORIZAÇÃO DE ORDENADORES DE DESPESA',
                                defaults={'status_choice': 'A PAGAR - AGUARDANDO AUTORIZAÇÃO DE ORDENADORES DE DESPESA'}
                            )

                            processo.status = status_padrao
                            processo.save()
                            return redirect('home_page')
                        else:
                            print("❌ Erros nas Notas Fiscais:", nota_fiscal_formset.errors)
                            print("❌ Erros nos Documentos:", documento_formset.errors)
                            raise Exception("Formulários secundários inválidos.")

                except Exception as e:
                    print(f"🛑 Erro CRÍTICO ao salvar no banco: {e}")
            else:
                print("❌ O Processo não salvou porque faltam dados:", processo_form.errors)

            nota_fiscal_formset = NotaFiscalFormSet(request.POST, prefix='nota_fiscal')
            documento_formset = DocumentoFormSet(request.POST, request.FILES, prefix='documento')
            retencao_formset = RetencaoFormSet(prefix='imposto')

            return render(request, 'add_process.html', {
                'processo_form': processo_form,
                'nota_fiscal_formset': nota_fiscal_formset,
                'documento_formset': documento_formset,
                'retencao_formset': retencao_formset
            })
    else:
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
    processo = get_object_or_404(Processo, id=processo_id)
    documentos = processo.documentos.all().order_by('ordem')

    lista_caminhos = []
    for doc in documentos:
        if doc.arquivo and os.path.exists(doc.arquivo.path):
            lista_caminhos.append(doc.arquivo.path)

    if not lista_caminhos:
        return HttpResponse("Este processo ainda não possui documentos em PDF anexados.", status=404)

    pdf_buffer = mesclar_pdfs_em_memoria(lista_caminhos)

    if pdf_buffer:
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        nome_arquivo = f"Processo_{processo.n_nota_empenho or processo.id}.pdf"
        response['Content-Disposition'] = f'inline; filename="{nome_arquivo}"'
        return response
    else:
        return HttpResponse("Erro interno ao mesclar os PDFs.", status=500)


def editar_processo(request, pk):
    processo = get_object_or_404(Processo, id=pk)

    if request.method == 'POST':
        processo_form = ProcessoForm(request.POST, instance=processo, prefix='processo')
        nota_fiscal_formset = NotaFiscalFormSet(request.POST, instance=processo, prefix='nota_fiscal')
        documento_formset = DocumentoFormSet(request.POST, request.FILES, instance=processo, prefix='documento')
        retencao_formset = RetencaoFormSet(request.POST, prefix='imposto')

        if processo_form.is_valid() and nota_fiscal_formset.is_valid() and documento_formset.is_valid():
            try:
                with transaction.atomic():
                    processo = processo_form.save()
                    notas = nota_fiscal_formset.save()
                    documento_formset.save()

                    for index, nota in enumerate(nota_fiscal_formset.queryset):
                        codigos = request.POST.getlist(f'imposto_{index}_code')
                        valores = request.POST.getlist(f'imposto_{index}_value')
                        rendimentos = request.POST.getlist(f'imposto_{index}_rendimento')
                        nota.retencoes.all().delete()

                        for c, r, v in zip(codigos, rendimentos, valores):
                            if c and v:
                                RetencaoImposto.objects.create(
                                    nota_fiscal=nota,
                                    codigo_id=c,
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


def contas_a_pagar(request):
    # --- BUG DO FILTRO CORRIGIDO COM __in ---
    processos_pendentes = Processo.objects.filter(
        status__status_choice__in=[
            'A PAGAR - AGUARDANDO AUTORIZAÇÃO DE ORDENADORES DE DESPESA',
            'A PAGAR - AUTORIZADO POR ORDENADORES DE DESPESA'
        ]
    )

    datas_agrupadas = processos_pendentes.values('data_pagamento').annotate(
        total=Count('id')
    ).order_by('data_pagamento')

    data_selecionada = request.GET.get('data')

    if data_selecionada:
        if data_selecionada == 'sem_data':
            lista_processos = processos_pendentes.filter(data_pagamento__isnull=True)
        else:
            lista_processos = processos_pendentes.filter(data_pagamento=data_selecionada)
    else:
        lista_processos = processos_pendentes

    context = {
        'datas_agrupadas': datas_agrupadas,
        'lista_processos': lista_processos,
        'data_selecionada': data_selecionada,
    }

    return render(request, 'contas_a_pagar.html', context)


def api_processar_boleto(request):
    if request.method == 'POST' and request.FILES.get('boleto_pdf'):
        pdf_file = request.FILES['boleto_pdf']
        try:
            dados = processar_pdf_boleto(pdf_file)
            return JsonResponse({'sucesso': True, 'dados': dados})
        except Exception as e:
            return JsonResponse({'sucesso': False, 'erro': str(e)})
    return JsonResponse({'sucesso': False, 'erro': 'Arquivo inválido ou não enviado.'})


def add_pre_empenho_view(request):
    if request.method == 'POST':
        processo_form = ProcessoForm(request.POST)

        if processo_form.is_valid():
            try:
                with transaction.atomic():
                    processo = processo_form.save(commit=False)

                    # --- STATUS ATUALIZADO (consertado campo nome para status_choice) ---
                    status_pre_empenho, created = StatusChoicesProcesso.objects.get_or_create(
                        status_choice__iexact='A EMPENHAR',
                        defaults={'status_choice': 'A EMPENHAR'}
                    )

                    processo.status = status_pre_empenho
                    processo.save()

                    messages.success(request, "Processo salvo com sucesso na fase de Pré-Empenho!")
                    return redirect('home_page')

            except Exception as e:
                messages.error(request, f"Erro ao salvar: {e}")
        else:
            messages.error(request, "Verifique os erros no formulário.")

    else:
        processo_form = ProcessoForm()

    context = {
        'processo_form': processo_form,
    }

    return render(request, 'add_pre_empenho.html', context)


def a_empenhar_view(request):
    # --- STATUS ATUALIZADO ---
    processos_pendentes = Processo.objects.filter(
        status__status_choice__iexact='A EMPENHAR'
    ).order_by('data_vencimento', '-id')

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
            return redirect('home_page')
        else:
            messages.error(request, "Erro ao cadastrar. Verifique os campos.")
    else:
        form = CredorForm()

    return render(request, 'add_credor.html', {'form': form})


def credores_list_view(request):
    queryset = Credor.objects.all().order_by('nome')
    meu_filtro = CredorFilter(request.GET, queryset=queryset)

    context = {
        'filter': meu_filtro,
        'credores': meu_filtro.qs,
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
    return render(request, 'verbas_panel.html')


def agrupar_verbas_view(request, tipo_verba):
    if request.method != 'POST':
        return redirect('verbas_panel')

    selecionados = request.POST.getlist('verbas_selecionadas')

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

    itens = ModeloVerba.objects.filter(id__in=selecionados, processo__isnull=True)

    if not itens.exists():
        messages.warning(request, "Os itens selecionados já possuem processo ou são inválidos.")
        return redirect(url_retorno)

    total = sum(item.valor_total for item in itens if item.valor_total)
    credor_nome = itens.first().beneficiario.nome

    # --- STATUS ATUALIZADO PARA AGRUPAMENTOS ---
    status_padrao, _ = StatusChoicesProcesso.objects.get_or_create(
        status_choice__iexact='A PAGAR - AGUARDANDO AUTORIZAÇÃO DE ORDENADORES DE DESPESA',
        defaults={'status_choice': 'A PAGAR - AGUARDANDO AUTORIZAÇÃO DE ORDENADORES DE DESPESA'}
    )

    novo_processo = Processo.objects.create(
        credor=credor_nome,
        valor_bruto=total,
        valor_liquido=total,
        detalhamento=f"Agrupamento de {tipo_verba.capitalize()}s",
        status=status_padrao
    )

    for item in itens:
        item.processo = novo_processo
        item.save()

        for doc in item.documentos.all():
            DocumentoProcesso.objects.create(
                processo=novo_processo,
                arquivo=doc.arquivo,
                tipo=doc.tipo,
                ordem=doc.ordem
            )

    messages.success(request, f"Processo #{novo_processo.id} gerado com sucesso! Os documentos foram importados.")
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

    if visao == 'processos':
        retencoes = RetencaoImposto.objects.filter(nota_fiscal__processo__id__in=selecionados)
    elif visao == 'notas':
        retencoes = RetencaoImposto.objects.filter(nota_fiscal__id__in=selecionados)
    else:
        retencoes = RetencaoImposto.objects.filter(id__in=selecionados)

    for retencao in retencoes:
        if retencao.valor:
            total_impostos += retencao.valor

    if total_impostos <= 0:
        messages.warning(request, "Os itens selecionados não possuem valores válidos.")
        return redirect('painel_impostos')

    # --- STATUS ATUALIZADO PARA AGRUPAMENTOS ---
    status_padrao, _ = StatusChoicesProcesso.objects.get_or_create(
        status_choice__iexact='A PAGAR - AGUARDANDO AUTORIZAÇÃO DE ORDENADORES DE DESPESA',
        defaults={'status_choice': 'A PAGAR - AGUARDANDO AUTORIZAÇÃO DE ORDENADORES DE DESPESA'}
    )

    novo_processo = Processo.objects.create(
        credor="Órgão Arrecadador (A Definir)",
        valor_bruto=total_impostos,
        valor_liquido=total_impostos,
        detalhamento="Pagamento Agrupado de Impostos Retidos",
        observacao="Gerado automaticamente.",
        status=status_padrao
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
        queryset_base = RetencaoImposto.objects.all().order_by('-id')
        meu_filtro = RetencaoIndividualFilter(request.GET, queryset=queryset_base)
        itens = meu_filtro.qs.select_related('codigo', 'status', 'nota_fiscal', 'nota_fiscal__processo')

    context = {
        'visao': visao,
        'meu_filtro': meu_filtro,
        'itens': itens,
    }

    return render(request, 'painel_impostos.html', context)


def painel_comprovantes_view(request):
    processos_autorizados = Processo.objects.filter(
        status__status_choice__iexact='A PAGAR - AUTORIZADO POR ORDENADORES DE DESPESA'
    ).values('id', 'credor', 'valor_liquido', 'n_nota_empenho')

    context = {
        'processos_json': json.dumps(list(processos_autorizados), default=str)
    }
    return render(request, 'painel_comprovantes.html', context)


def api_fatiar_comprovantes(request):
    if request.method == 'POST' and request.FILES.get('pdf_banco'):
        try:
            resultados = processar_pdf_comprovantes_ia(request.FILES['pdf_banco'])
            return JsonResponse({'sucesso': True, 'comprovantes': resultados})
        except Exception as e:
            return JsonResponse({'sucesso': False, 'erro': str(e)})
    return JsonResponse({'sucesso': False, 'erro': 'Arquivo não enviado.'})


@transaction.atomic
def api_vincular_comprovantes(request):
    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            vinculos = dados.get('vinculos', [])

            # --- STATUS ATUALIZADO ---
            status_pago, _ = StatusChoicesProcesso.objects.get_or_create(
                status_choice__iexact='PAGO - EM CONFERÊNCIA',
                defaults={'status_choice': 'PAGO - EM CONFERÊNCIA'}
            )

            tipo_comprovante, _ = TiposDeDocumento.objects.get_or_create(
                tipo_de_documento__iexact='Comprovante de Pagamento',
                defaults={'tipo_de_documento': 'Comprovante de Pagamento'}
            )

            processos_atualizados = 0
            processos_barrados = 0

            for vinculo in vinculos:
                processo_id = vinculo.get('processo_id')
                temp_path = vinculo.get('temp_path')

                if not processo_id or not temp_path:
                    continue

                processo = Processo.objects.get(id=processo_id)

                if not processo.status or processo.status.status_choice.upper() != 'A PAGAR - AUTORIZADO POR ORDENADORES DE DESPESA':
                    processos_barrados += 1
                    continue

                if default_storage.exists(temp_path):
                    with default_storage.open(temp_path) as temp_file:
                        DocumentoProcesso.objects.create(
                            processo=processo,
                            arquivo=ContentFile(temp_file.read(), name=f"Comprovante_Proc_{processo.id}.pdf"),
                            tipo=tipo_comprovante,
                            ordem=99
                        )
                    default_storage.delete(temp_path)

                processo.status = status_pago
                processo.save()
                processos_atualizados += 1

            msg_final = f'{processos_atualizados} processo(s) baixado(s) com sucesso!'
            if processos_barrados > 0:
                msg_final += f' (Atenção: {processos_barrados} bloqueados por falta de autorização do Ordenador).'

            return JsonResponse({'sucesso': True, 'mensagem': msg_final})

        except Exception as e:
            return JsonResponse({'sucesso': False, 'erro': str(e)})

    return JsonResponse({'sucesso': False, 'erro': 'Método inválido.'})


def painel_conferencia_view(request):
    # --- STATUS ATUALIZADO ---
    processos_pagos = Processo.objects.filter(
        status__status_choice__iexact='PAGO - EM CONFERÊNCIA'
    )

    processos_aptos = processos_pagos.annotate(
        total_pendencias=Count('pendencias', distinct=True),
        pendencias_resolvidas=Count(
            'pendencias',
            filter=Q(pendencias__status__status_choice__iexact='RESOLVIDO'),
            distinct=True
        ),

        total_retencoes=Count('notas_fiscais__retencoes', distinct=True),
        retencoes_pagas=Count(
            'notas_fiscais__retencoes',
            filter=Q(notas_fiscais__retencoes__status__status_choice__iexact='PAGO'),
            distinct=True
        )
    ).filter(
        total_pendencias=F('pendencias_resolvidas'),
        total_retencoes=F('retencoes_pagas')
    ).order_by('data_pagamento')

    context = {
        'processos': processos_aptos
    }
    return render(request, 'conferencia.html', context)


def aprovar_conferencia_view(request, pk):
    if request.method == 'POST':
        processo = get_object_or_404(Processo, id=pk)

        # --- STATUS ATUALIZADO ---
        status_contabilizado, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact='CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL',
            defaults={'status_choice': 'CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL'}
        )

        processo.status = status_contabilizado
        processo.save()

        messages.success(request, f'Processo #{processo.id} aprovado na conferência e enviado para a contabilidade!')

    return redirect('painel_conferencia')


def enviar_para_autorizacao(request):
    if request.method == 'POST':
        selecionados = request.POST.getlist('processos_selecionados')

        if selecionados:
            status_aguardando, _ = StatusChoicesProcesso.objects.get_or_create(
                status_choice__iexact='A PAGAR - AGUARDANDO AUTORIZAÇÃO DE ORDENADORES DE DESPESA',
                defaults={'status_choice': 'A PAGAR - AGUARDANDO AUTORIZAÇÃO DE ORDENADORES DE DESPESA'}
            )

            Processo.objects.filter(id__in=selecionados).update(status=status_aguardando)
            messages.success(request, f'{len(selecionados)} processo(s) enviado(s) para autorização com sucesso.')
        else:
            messages.warning(request, 'Nenhum processo foi selecionado.')

    return redirect('contas_a_pagar')


def painel_autorizacao_view(request):
    processos = Processo.objects.filter(
        status__status_choice__iexact='A PAGAR - AGUARDANDO AUTORIZAÇÃO DE ORDENADORES DE DESPESA'
    ).order_by('data_pagamento', 'id')

    return render(request, 'autorizacao.html', {'processos': processos})


def autorizar_pagamento(request):
    if request.method == 'POST':
        selecionados = request.POST.getlist('processos_selecionados')

        if selecionados:
            status_autorizado, _ = StatusChoicesProcesso.objects.get_or_create(
                status_choice__iexact='A PAGAR - AUTORIZADO POR ORDENADORES DE DESPESA',
                defaults={'status_choice': 'A PAGAR - AUTORIZADO POR ORDENADORES DE DESPESA'}
            )

            Processo.objects.filter(id__in=selecionados).update(status=status_autorizado)
            messages.success(request, f'{len(selecionados)} pagamento(s) autorizado(s) com sucesso!')
        else:
            messages.warning(request, 'Nenhum processo foi selecionado para autorização.')

    return redirect('painel_autorizacao')

def aprovar_conferencia_view(request, pk):
    """Muda o status do processo após a conferência e o envia para a CONTABILIZAÇÃO"""
    if request.method == 'POST':
        processo = get_object_or_404(Processo, id=pk)

        status_contabilizar, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact='PAGO - A CONTABILIZAR',
            defaults={'status_choice': 'PAGO - A CONTABILIZAR'}
        )

        processo.status = status_contabilizar
        processo.save()
        messages.success(request, f'Processo #{processo.id} aprovado na conferência e enviado para Contabilização!')

    return redirect('painel_conferencia')


# ==========================================
# RETA FINAL DO PROCESSO
# ==========================================

def painel_contabilizacao_view(request):
    processos = Processo.objects.filter(status__status_choice__iexact='PAGO - A CONTABILIZAR').order_by('data_pagamento')
    return render(request, 'contabilizacao.html', {'processos': processos})

def aprovar_contabilizacao_view(request, pk):
    if request.method == 'POST':
        processo = get_object_or_404(Processo, id=pk)
        status_conselho, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact='CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL',
            defaults={'status_choice': 'CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL'}
        )
        processo.status = status_conselho
        processo.save()
        messages.success(request, f'Processo #{processo.id} contabilizado e enviado ao Conselho Fiscal!')
    return redirect('painel_contabilizacao')

def painel_conselho_view(request):
    processos = Processo.objects.filter(status__status_choice__iexact='CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL').order_by('data_pagamento')
    return render(request, 'conselho.html', {'processos': processos})

def aprovar_conselho_view(request, pk):
    if request.method == 'POST':
        processo = get_object_or_404(Processo, id=pk)
        status_arquivamento, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact='APROVADO POR CONSELHO FISCAL - PARA ARQUIVAMENTO',
            defaults={'status_choice': 'APROVADO POR CONSELHO FISCAL - PARA ARQUIVAMENTO'}
        )
        processo.status = status_arquivamento
        processo.save()
        messages.success(request, f'Processo #{processo.id} aprovado pelo Conselho e liberado para arquivamento!')
    return redirect('painel_conselho')

def painel_arquivamento_view(request):
    processos = Processo.objects.filter(status__status_choice__iexact='APROVADO POR CONSELHO FISCAL - PARA ARQUIVAMENTO').order_by('data_pagamento')
    return render(request, 'arquivamento.html', {'processos': processos})

def arquivar_processo_view(request, pk):
    if request.method == 'POST':
        processo = get_object_or_404(Processo, id=pk)
        status_arquivado, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact='ARQUIVADO',
            defaults={'status_choice': 'ARQUIVADO'}
        )
        processo.status = status_arquivado
        processo.save()
        messages.success(request, f'Processo #{processo.id} devidamente ARQUIVADO. Ciclo encerrado!')
    return redirect('painel_arquivamento')

def painel_suprimentos_view(request):
    """Lista todos os suprimentos ativos e fechados."""
    suprimentos = SuprimentoDeFundos.objects.all().order_by('-id')
    return render(request, 'suprimentos_list.html', {'suprimentos': suprimentos})


def gerenciar_suprimento_view(request, pk):
    """A tela principal onde o suprido lança as despesas ao longo do mês."""
    suprimento = get_object_or_404(SuprimentoDeFundos, id=pk)
    despesas = suprimento.despesas.all().order_by('data', 'id')

    if request.method == 'POST':
        # Captura os textos
        data = request.POST.get('data')
        estabelecimento = request.POST.get('estabelecimento')
        detalhamento = request.POST.get('detalhamento')
        nota_fiscal = request.POST.get('nota_fiscal')
        valor = request.POST.get('valor').replace(',', '.')

        # Captura o arquivo único
        arquivo_pdf = request.FILES.get('arquivo')

        if data and valor and detalhamento:
            DespesaSuprimento.objects.create(
                suprimento=suprimento,
                data=data,
                estabelecimento=estabelecimento,
                detalhamento=detalhamento,
                nota_fiscal=nota_fiscal,
                valor=float(valor),
                arquivo=arquivo_pdf  # Salva o PDF atrelado à despesa
            )
            messages.success(request, 'Despesa e documento anexados com sucesso!')
            return redirect('gerenciar_suprimento', pk=suprimento.id)

    context = {
        'suprimento': suprimento,
        'despesas': despesas
    }
    return render(request, 'gerenciar_suprimento.html', context)

def fechar_suprimento_view(request, pk):
    """Encerra a prestação de contas e manda para a Conferência."""
    if request.method == 'POST':
        suprimento = get_object_or_404(SuprimentoDeFundos, id=pk)
        processo = suprimento.processo

        # Pega o status de conferência que criamos no passo anterior
        status_conferencia, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact='PAGO - EM CONFERÊNCIA',
            defaults={'status_choice': 'PAGO - EM CONFERÊNCIA'}
        )

        # Se houver um processo atrelado, joga ele para a fila da Auditoria
        if processo:
            processo.status = status_conferencia
            # Atualiza o valor final do processo para refletir apenas o que foi gasto (se for a regra do seu órgão)
            # processo.valor_liquido = suprimento.valor_gasto
            processo.save()

        messages.success(request,
                         f'Prestação de contas do suprimento #{suprimento.id} encerrada e enviada para Conferência!')
        return redirect('painel_suprimentos')

def add_suprimento_view(request):
    if request.method == 'POST':
        form = SuprimentoForm(request.POST)

        if form.is_valid():
            try:
                suprimento = form.save()
                messages.success(request, 'Suprimento de Fundos cadastrado com sucesso!')
                # Redireciona de volta para a lista após criar
                return redirect('painel_suprimentos')
            except Exception as e:
                messages.error(request, f'Erro ao salvar: {e}')
        else:
            messages.error(request, 'Verifique os erros no formulário.')
    else:
        form = SuprimentoForm()

    return render(request, 'add_suprimento.html', {'form': form})