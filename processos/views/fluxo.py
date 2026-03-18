import io
import os
import json
import random
import tempfile
import zipfile
from datetime import date, datetime, timedelta
from decimal import Decimal
from faker import Faker
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, Q, F, Sum, Exists, OuterRef
from pypdf import PdfWriter
from ..forms import ProcessoForm, DocumentoFormSet, DocumentoFiscalFormSet, RetencaoFormSet, CredorForm, DiariaForm,ReembolsoForm, JetonForm, AuxilioForm, SuprimentoForm, PendenciaForm, PendenciaFormSet
from ..validators import verificar_turnpike
from ..utils import extract_siscac_data, mesclar_pdfs_em_memoria, processar_pdf_boleto, processar_pdf_comprovantes, gerar_termo_auditoria, fatiar_pdf_manual, processar_pdf_comprovantes_ia, gerar_pdf_autorizacao, gerar_pdf_conselho_fiscal, gerar_pdf_pcd
from ..ai_utils import extrair_dados_documento, extract_data_with_llm, extrair_codigos_barras_boletos
from ..invoice_processor import process_invoice_taxes
from ..models import Processo, DocumentoFiscal, StatusChoicesProcesso, Credor, Diaria, ReembolsoCombustivel, Jeton, AuxilioRepresentacao, TiposDeDocumento, DocumentoProcesso, DocumentoDiaria, DocumentoReembolso, DocumentoJeton, DocumentoAuxilio, CodigosImposto, RetencaoImposto, SuprimentoDeFundos, DespesaSuprimento, StatusChoicesPendencias, Pendencia, TiposDePendencias, ComprovanteDePagamento, Tabela_Valores_Unitarios_Verbas_Indenizatorias, DocumentoSuprimentoDeFundos, TiposDePagamento, Contingencia, StatusChoicesVerbasIndenizatorias, StatusChoicesRetencoes, MeiosDeTransporte, FormasDePagamento, ContasBancarias, Grupos, CargosFuncoes, TagChoices
from ..filters import ProcessoFilter, CredorFilter, DiariaFilter, ReembolsoFilter, JetonFilter, AuxilioFilter, RetencaoProcessoFilter, RetencaoNotaFilter, RetencaoIndividualFilter, PendenciaFilter, DocumentoFiscalFilter, ContingenciaFilter, DiariasAutorizacaoFilter

# ==========================================
# STATUS RESTRICTIONS FOR PROCESS EDITING
# ==========================================

# Processes in these statuses are archived/historical and cannot be edited at all.
STATUS_BLOQUEADOS_TOTAL = {
    'CANCELADO / ANULADO',
    'ARQUIVADO',
    'APROVADO - PENDENTE ARQUIVAMENTO',
    'CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL',
}

# Processes in these statuses have been authorised for payment.
# Only document inclusion and reordering is permitted; all other fields are locked.
STATUS_SOMENTE_DOCUMENTOS = {
    'LANÇADO - AGUARDANDO COMPROVANTE',
    'PAGO - EM CONFERÊNCIA',
    'A PAGAR - AUTORIZADO',
    'A PAGAR - ENVIADO PARA AUTORIZAÇÃO',
}


def home_page(request):
    processos_base = Processo.objects.all().order_by('-id')
    meu_filtro = ProcessoFilter(request.GET, queryset=processos_base)
    processos_filtrados = meu_filtro.qs

    context = {
        'lista_processos': processos_filtrados,
        'meu_filtro': meu_filtro,
    }
    return render(request, 'home.html', context)


import unicodedata


def _normalizar_texto(texto):
    """Remove acentos e converte para maiúsculas para comparações robustas."""
    return unicodedata.normalize('NFD', texto.upper()).encode('ascii', 'ignore').decode('ascii')


def _extrair_e_salvar_codigos_barras(processo):
    """
    Se o forma_pagamento do processo for Boleto Bancário ou Gerenciador, percorre todos
    os DocumentoProcesso do tipo boleto, extrai os códigos de barras via IA (mesclando
    os PDFs num único envio) e persiste o resultado em DocumentoProcesso.codigo_barras.

    Returns:
        Tupla (n_extraidos, n_falhas).
    """
    if not processo.forma_pagamento:
        return 0, 0

    forma_str = _normalizar_texto(processo.forma_pagamento.forma_de_pagamento)
    if 'BOLETO' not in forma_str and 'GERENCIADOR' not in forma_str:
        return 0, 0

    boleto_docs = [
        doc for doc in processo.documentos.select_related('tipo').all()
        if 'boleto' in doc.tipo.tipo_de_documento.lower()
    ]

    if not boleto_docs:
        return 0, 0

    caminhos = []
    docs_validos = []
    for doc in boleto_docs:
        try:
            caminhos.append(doc.arquivo.path)
            docs_validos.append(doc)
        except Exception:
            pass

    if not caminhos:
        return 0, 0

    barcodes = extrair_codigos_barras_boletos(caminhos)
    if barcodes is None:
        return 0, len(docs_validos)

    n_docs = len(docs_validos)
    extraidos = 0
    falhas = 0
    for doc, barcode in zip(docs_validos, barcodes):
        if barcode:
            # Truncate to model's max_length (DocumentoProcesso.codigo_barras = max 60 chars)
            doc.codigo_barras = str(barcode)[:60]
            doc.save(update_fields=['codigo_barras'])
            extraidos += 1
        else:
            falhas += 1

    # If the LLM returned fewer items than docs (zip stops at the shorter list),
    # the remaining unprocessed documents are counted as failures.
    falhas += n_docs - (extraidos + falhas)

    return extraidos, falhas


# ==========================================
# CAPA E DOCUMENTOS DO PROCESSO
# ==========================================
def add_process_view(request):
    initial_data = {}
    siscac_temp_path = None

    if request.method == 'POST':
        btn_extract = 'btn_extract' in request.POST
        trigger_a_empenhar = request.POST.get('trigger_a_empenhar') == 'on'

        if btn_extract and request.FILES.get('siscac_file'):
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
            documento_formset = DocumentoFormSet(prefix='documento')
            pendencia_formset = PendenciaFormSet(prefix='pendencia')

            return render(request, 'fluxo/add_process.html', {
                'processo_form': processo_form,
                'documento_formset': documento_formset,
                'pendencia_formset': pendencia_formset,
                'extracted_msg': "Dados extraídos! O arquivo SISCAC será anexado automaticamente ao salvar.",
                'next_url': request.POST.get('next', ''),
            })

        else:
            processo_form = ProcessoForm(request.POST, prefix='processo')
            documento_formset = DocumentoFormSet(request.POST, request.FILES, prefix='documento')
            pendencia_formset = PendenciaFormSet(request.POST, prefix='pendencia')

            if processo_form.is_valid() and documento_formset.is_valid() and pendencia_formset.is_valid():
                is_extra = processo_form.cleaned_data.get('extraorcamentario')

                # Validate documento orçamentário before entering the transaction
                if not is_extra and not trigger_a_empenhar:
                    has_orcamentario = any(
                        f.cleaned_data
                        and not f.cleaned_data.get('DELETE', False)
                        and f.cleaned_data.get('tipo')
                        and 'orçament' in f.cleaned_data['tipo'].tipo_de_documento.lower()
                        for f in documento_formset.forms
                    )
                    if not has_orcamentario:
                        messages.error(
                            request,
                            'É necessário anexar um Documento Orçamentário para prosseguir. '
                            'Se o processo for Extraorçamentário ou "A Empenhar", selecione a opção correspondente.'
                        )
                        return render(request, 'fluxo/add_process.html', {
                            'processo_form': processo_form,
                            'documento_formset': documento_formset,
                            'pendencia_formset': pendencia_formset
                        })

                try:
                    with transaction.atomic():
                        processo = processo_form.save(commit=False)

                        if trigger_a_empenhar:
                            status_obj, _ = StatusChoicesProcesso.objects.get_or_create(
                                status_choice__iexact='A EMPENHAR', defaults={'status_choice': 'A EMPENHAR'}
                            )
                            processo.status = status_obj
                            processo.n_nota_empenho = None
                            processo.data_empenho = None
                            processo.ano_exercicio = None

                        elif is_extra:
                            status_obj, _ = StatusChoicesProcesso.objects.get_or_create(
                                status_choice__iexact='A PAGAR - PENDENTE AUTORIZAÇÃO',
                                defaults={'status_choice': 'A PAGAR - PENDENTE AUTORIZAÇÃO'}
                            )
                            processo.status = status_obj
                            processo.n_nota_empenho = None
                            processo.data_empenho = None
                            processo.ano_exercicio = None

                        else:
                            status_obj, _ = StatusChoicesProcesso.objects.get_or_create(
                                status_choice__iexact='A PAGAR - PENDENTE AUTORIZAÇÃO',
                                defaults={'status_choice': 'A PAGAR - PENDENTE AUTORIZAÇÃO'}
                            )
                            processo.status = status_obj

                        processo.save()

                        documento_formset.instance = processo
                        pendencia_formset.instance = processo
                        documento_formset.save()
                        pendencia_formset.save()

                    # Extrai códigos de barras dos boletos fora da transação para não
                    # bloquear a conexão com o banco durante a chamada à IA.
                    try:
                        n_extraidos, n_falhas = _extrair_e_salvar_codigos_barras(processo)
                        if n_extraidos > 0:
                            messages.info(request, f"{n_extraidos} código(s) de barras extraído(s) dos boletos automaticamente.")
                        if n_falhas > 0:
                            messages.warning(request, f"Não foi possível extrair o código de barras de {n_falhas} boleto(s). Preencha manualmente se necessário.")
                    except Exception as barcode_err:
                        print(f"⚠️ Erro na extração de códigos de barras: {barcode_err}", flush=True)

                    messages.success(request, f"Processo #{processo.id} inserido com sucesso!")
                    if request.POST.get('btn_goto_fiscais'):
                        return redirect('documentos_fiscais', pk=processo.id)
                    next_url = request.POST.get('next', '')
                    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                        return redirect(next_url)
                    return redirect('home_page')

                except Exception as e:
                    print(f"🛑 Erro CRÍTICO de Banco de Dados ao salvar: {e}", flush=True)
                    messages.error(request, "Ocorreu um erro interno ao salvar no banco de dados.")

            else:
                messages.error(request, "Verifique os erros no formulário (Documentos ou Capa).")

            return render(request, 'fluxo/add_process.html', {
                'processo_form': processo_form,
                'documento_formset': documento_formset,
                'pendencia_formset': pendencia_formset,
                'next_url': request.POST.get('next', ''),
            })

    else:
        processo_form = ProcessoForm(prefix='processo')
        documento_formset = DocumentoFormSet(prefix='documento')
        pendencia_formset = PendenciaFormSet(prefix='pendencia')
        next_url = request.META.get('HTTP_REFERER', '')

        return render(request, 'fluxo/add_process.html', {
            'processo_form': processo_form,
            'documento_formset': documento_formset,
            'pendencia_formset': pendencia_formset,
            'next_url': next_url,
        })


def editar_processo(request, pk):
    processo = get_object_or_404(Processo, id=pk)
    status_inicial = processo.status.status_choice.upper() if processo.status else ''

    # Tier 1: Archive / historical – editing is completely blocked.
    if status_inicial in STATUS_BLOQUEADOS_TOTAL:
        messages.error(
            request,
            f'O processo #{pk} está em status "{processo.status}" e não pode ser editado. '
            'Alterações nesses processos devem ser tratadas pela interface de contingência.'
        )
        return redirect('home_page')

    # Redirect to the dedicated verbas page when this processo is of tipo "VERBAS INDENIZATÓRIAS"
    if (
        processo.tipo_pagamento
        and processo.tipo_pagamento.tipo_de_pagamento.upper() == 'VERBAS INDENIZATÓRIAS'
    ):
        return redirect('editar_processo_verbas', pk=pk)

    # Tier 2: Authorised-for-payment – only document inclusion/reordering is allowed.
    somente_documentos = status_inicial in STATUS_SOMENTE_DOCUMENTOS

    if request.method == 'POST':
        documento_formset = DocumentoFormSet(request.POST, request.FILES, instance=processo, prefix='documento')

        if somente_documentos:
            # Only save document changes; process metadata is left untouched.
            if documento_formset.is_valid():
                try:
                    with transaction.atomic():
                        documento_formset.save()

                    # Extrai códigos de barras de novos boletos fora da transação.
                    try:
                        n_extraidos, n_falhas = _extrair_e_salvar_codigos_barras(processo)
                        if n_extraidos > 0:
                            messages.info(request, f"{n_extraidos} código(s) de barras extraído(s) dos boletos automaticamente.")
                        if n_falhas > 0:
                            messages.warning(request, f"Não foi possível extrair o código de barras de {n_falhas} boleto(s). Preencha manualmente se necessário.")
                    except Exception as barcode_err:
                        print(f"⚠️ Erro na extração de códigos de barras: {barcode_err}", flush=True)

                    messages.success(request, f'Documentos do Processo #{pk} atualizados com sucesso!')
                    return redirect('editar_processo', pk=pk)
                except Exception as e:
                    print(f"🛑 Erro ao atualizar documentos: {e}")
                    messages.error(request, 'Erro interno ao salvar os documentos.')
            else:
                messages.error(request, 'Verifique os erros nos documentos.')
            processo_form = ProcessoForm(instance=processo, prefix='processo')
            pendencia_formset = PendenciaFormSet(instance=processo, prefix='pendencia')
        else:
            # Tier 3: Full editing.
            confirmar_extra = request.POST.get('confirmar_extra_orcamentario') == 'on'
            processo_form = ProcessoForm(request.POST, instance=processo, prefix='processo')
            pendencia_formset = PendenciaFormSet(request.POST, instance=processo, prefix='pendencia')

            if processo_form.is_valid() and documento_formset.is_valid() and pendencia_formset.is_valid():
                try:
                    with transaction.atomic():
                        processo_saved = processo_form.save(commit=False)

                        # When confirming extra-budgetary change from 'A EMPENHAR' status,
                        # override status and clear budget fields
                        if confirmar_extra and status_inicial == 'A EMPENHAR':
                            status_obj, _ = StatusChoicesProcesso.objects.get_or_create(
                                status_choice__iexact='A PAGAR - PENDENTE AUTORIZAÇÃO',
                                defaults={'status_choice': 'A PAGAR - PENDENTE AUTORIZAÇÃO'}
                            )
                            processo_saved.status = status_obj
                            processo_saved.extraorcamentario = True
                            processo_saved.n_nota_empenho = None
                            processo_saved.data_empenho = None
                            processo_saved.ano_exercicio = None

                        processo_saved.save()
                        documento_formset.save()
                        pendencia_formset.save()

                    # Extrai códigos de barras dos boletos fora da transação para não
                    # bloquear a conexão com o banco durante a chamada à IA.
                    try:
                        n_extraidos, n_falhas = _extrair_e_salvar_codigos_barras(processo_saved)
                        if n_extraidos > 0:
                            messages.info(request, f"{n_extraidos} código(s) de barras extraído(s) dos boletos automaticamente.")
                        if n_falhas > 0:
                            messages.warning(request, f"Não foi possível extrair o código de barras de {n_falhas} boleto(s). Preencha manualmente se necessário.")
                    except Exception as barcode_err:
                        print(f"⚠️ Erro na extração de códigos de barras: {barcode_err}", flush=True)

                    messages.success(request, f'Processo #{processo_saved.id} atualizado com sucesso!')
                    return redirect('editar_processo', pk=processo_saved.id)

                except Exception as e:
                    print(f"🛑 Erro ao atualizar no banco: {e}")
                    messages.error(request, 'Erro interno ao salvar as alterações.')
            else:
                messages.error(request, 'Verifique os erros no formulário.')

    else:
        processo_form = ProcessoForm(instance=processo, prefix='processo')
        documento_formset = DocumentoFormSet(instance=processo, prefix='documento')
        pendencia_formset = PendenciaFormSet(instance=processo, prefix='pendencia')

    context = {
        'processo_form': processo_form,
        'documento_formset': documento_formset,
        'pendencia_formset': pendencia_formset,
        'processo': processo,
        'status_inicial': status_inicial,
        'somente_documentos': somente_documentos,
        'aguardando_liquidacao': status_inicial.startswith('AGUARDANDO LIQUIDAÇÃO'),
        'documentos_fiscais_url': reverse('documentos_fiscais', kwargs={'pk': processo.id}),
    }

    return render(request, 'fluxo/editar_processo.html', context)


# ==========================================
# DOCUMENTOS FISCAIS: GERENCIAMENTO DE NOTAS FISCAIS
# ==========================================
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


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def contas_a_pagar(request):
    STATUSES_CONTAS_A_PAGAR = [
        'A PAGAR - PENDENTE AUTORIZAÇÃO',
        'A PAGAR - ENVIADO PARA AUTORIZAÇÃO',
        'A PAGAR - AUTORIZADO',
        'LANÇADO - AGUARDANDO COMPROVANTE',
    ]

    processos_pendentes = Processo.objects.filter(
        status__status_choice__in=STATUSES_CONTAS_A_PAGAR
    )

    datas_agrupadas = processos_pendentes.values('data_pagamento').annotate(
        total=Count('id')
    ).order_by('data_pagamento')

    formas_agrupadas = processos_pendentes.values(
        'forma_pagamento__id',
        'forma_pagamento__forma_de_pagamento'
    ).annotate(
        total=Count('id')
    ).order_by('forma_pagamento__forma_de_pagamento')

    statuses_agrupados = processos_pendentes.values(
        'status__status_choice'
    ).annotate(
        total=Count('id')
    ).order_by('status__status_choice')

    data_selecionada = request.GET.get('data')
    forma_selecionada = request.GET.get('forma')
    status_selecionado = request.GET.get('status')

    lista_processos = processos_pendentes

    if status_selecionado:
        lista_processos = lista_processos.filter(status__status_choice=status_selecionado)

    if data_selecionada:
        if data_selecionada == 'sem_data':
            lista_processos = lista_processos.filter(data_pagamento__isnull=True)
        else:
            lista_processos = lista_processos.filter(data_pagamento=data_selecionada)

    if forma_selecionada:
        if forma_selecionada == 'sem_forma':
            lista_processos = lista_processos.filter(forma_pagamento__isnull=True)
        else:
            try:
                lista_processos = lista_processos.filter(forma_pagamento__id=int(forma_selecionada))
            except (ValueError, TypeError):
                pass

    lista_processos = lista_processos.annotate(
        has_pendencias=Exists(Pendencia.objects.filter(processo=OuterRef('pk'))),
        has_retencoes=Exists(RetencaoImposto.objects.filter(nota_fiscal__processo=OuterRef('pk'))),
    )

    context = {
        'datas_agrupadas': datas_agrupadas,
        'formas_agrupadas': formas_agrupadas,
        'statuses_agrupados': statuses_agrupados,
        'lista_processos': lista_processos,
        'data_selecionada': data_selecionada,
        'forma_selecionada': forma_selecionada,
        'status_selecionado': status_selecionado,
        'pode_interagir': request.user.has_perm('processos.pode_operar_contas_pagar'),
    }

    return render(request, 'fluxo/contas_a_pagar.html', context)


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

    return render(request, 'fluxo/add_pre_empenho.html', context)


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def a_empenhar_view(request):
    if request.method == 'POST':
        pode_interagir = request.user.has_perm('processos.pode_operar_contas_pagar')
        if not pode_interagir:
            raise PermissionDenied
        processo_id = request.POST.get('processo_id')
        n_nota_empenho = request.POST.get('n_nota_empenho')
        data_empenho_str = request.POST.get('data_empenho')
        siscac_file = request.FILES.get('siscac_file')

        if processo_id and n_nota_empenho and data_empenho_str:
            try:
                with transaction.atomic():
                    processo = Processo.objects.get(id=processo_id)
                    processo.n_nota_empenho = n_nota_empenho
                    processo.data_empenho = datetime.strptime(data_empenho_str, '%Y-%m-%d').date()

                    if siscac_file:
                        tipo_doc, _ = TiposDeDocumento.objects.get_or_create(
                            tipo_de_documento__iexact='DOCUMENTOS ORÇAMENTÁRIOS',
                            defaults={'tipo_de_documento': 'DOCUMENTOS ORÇAMENTÁRIOS'}
                        )

                        for doc in processo.documentos.all().order_by('-ordem'):
                            doc.ordem += 1
                            doc.save()

                        DocumentoProcesso.objects.create(
                            processo=processo,
                            arquivo=siscac_file,
                            tipo=tipo_doc,
                            ordem=1
                        )

                    # Turnpike: check requirements before advancing status
                    erros_turnpike = verificar_turnpike(
                        processo,
                        status_anterior='A EMPENHAR',
                        status_novo='AGUARDANDO LIQUIDAÇÃO',
                    )
                    if erros_turnpike:
                        raise ValueError(' '.join(erros_turnpike))

                    status_aguardando, _ = StatusChoicesProcesso.objects.get_or_create(
                        status_choice__iexact='AGUARDANDO LIQUIDAÇÃO',
                        defaults={'status_choice': 'AGUARDANDO LIQUIDAÇÃO'}
                    )
                    processo.status = status_aguardando
                    processo.save()

                messages.success(request, f"Empenho registrado com sucesso! Processo #{processo.id} avançou para Aguardando Liquidação.")
            except Processo.DoesNotExist:
                messages.error(request, "Processo não encontrado.")
            except Exception as e:
                messages.error(request, f"Erro inesperado ao salvar empenho: {str(e)}")
        else:
            messages.error(request, "Por favor, preencha o número e a data da nota de empenho para avançar.")

        return redirect('a_empenhar')

    processos_pendentes = Processo.objects.filter(
        status__status_choice__iexact='A EMPENHAR'
    ).order_by('data_vencimento', '-id')

    context = {
        'processos': processos_pendentes,
        'pode_interagir': request.user.has_perm('processos.pode_operar_contas_pagar'),
    }
    return render(request, 'fluxo/a_empenhar.html', context)


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def avancar_para_pagamento_view(request, pk):
    """
    Advance a process from 'AGUARDANDO LIQUIDAÇÃO' to 'A PAGAR - PENDENTE AUTORIZAÇÃO'.
    Turnpike check: all documentos fiscais must be attested (atestada=True).
    """
    processo = get_object_or_404(Processo, id=pk)

    if request.method != 'POST':
        return redirect('editar_processo', pk=pk)

    status_atual = processo.status.status_choice.upper() if processo.status else ''

    if not status_atual.startswith('AGUARDANDO LIQUIDAÇÃO'):
        messages.error(
            request,
            f'O processo #{pk} não está em status "Aguardando Liquidação" '
            f'(status atual: "{processo.status}"). Ação não permitida.'
        )
        return redirect('editar_processo', pk=pk)

    erros_turnpike = verificar_turnpike(
        processo,
        status_anterior=status_atual,
        status_novo='A PAGAR - PENDENTE AUTORIZAÇÃO',
    )

    if erros_turnpike:
        for erro in erros_turnpike:
            messages.error(request, erro)
        return redirect('editar_processo', pk=pk)

    try:
        with transaction.atomic():
            status_pendente, _ = StatusChoicesProcesso.objects.get_or_create(
                status_choice__iexact='A PAGAR - PENDENTE AUTORIZAÇÃO',
                defaults={'status_choice': 'A PAGAR - PENDENTE AUTORIZAÇÃO'}
            )
            processo.status = status_pendente
            processo.save()

        messages.success(
            request,
            f'Processo #{pk} avançado com sucesso para "A Pagar - Pendente Autorização".'
        )
    except Exception as e:
        messages.error(request, f'Erro ao avançar o processo: {str(e)}')

    return redirect('editar_processo', pk=pk)


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def enviar_para_autorizacao(request):
    if request.method == 'POST':
        if not request.user.has_perm('processos.pode_operar_contas_pagar'):
            raise PermissionDenied
        selecionados = request.POST.getlist('processos_selecionados')

        if selecionados:
            elegiveis = Processo.objects.filter(
                id__in=selecionados,
                status__status_choice__iexact='A PAGAR - PENDENTE AUTORIZAÇÃO'
            )
            count_elegiveis = elegiveis.count()
            count_ignorados = len(selecionados) - count_elegiveis

            if count_elegiveis > 0:
                status_aguardando, _ = StatusChoicesProcesso.objects.get_or_create(
                    status_choice__iexact='A PAGAR - ENVIADO PARA AUTORIZAÇÃO',
                    defaults={'status_choice': 'A PAGAR - ENVIADO PARA AUTORIZAÇÃO'}
                )
                elegiveis.update(status=status_aguardando)
                messages.success(request, f'{count_elegiveis} processo(s) enviado(s) para autorização com sucesso.')
            else:
                messages.error(request, 'Nenhum dos processos selecionados está com status "A PAGAR - PENDENTE AUTORIZAÇÃO".')

            if count_ignorados > 0:
                messages.warning(
                    request,
                    f'{count_ignorados} processo(s) ignorado(s): apenas processos com status '
                    f'"A PAGAR - PENDENTE AUTORIZAÇÃO" podem ser enviados para autorização.'
                )
        else:
            messages.warning(request, 'Nenhum processo foi selecionado.')

    return redirect('contas_a_pagar')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def painel_autorizacao_view(request):
    processos = Processo.objects.filter(
        status__status_choice__iexact='A PAGAR - ENVIADO PARA AUTORIZAÇÃO'
    ).order_by('data_pagamento', 'id')

    processos_autorizados = Processo.objects.filter(
        status__status_choice__iexact='A PAGAR - AUTORIZADO'
    ).order_by('data_pagamento', 'id')

    context = {
        'processos': processos,
        'processos_autorizados': processos_autorizados,
        'pendencia_form': PendenciaForm(),
        'pode_interagir': request.user.has_perm('processos.pode_autorizar_pagamento'),
    }
    return render(request, 'fluxo/autorizacao.html', context)


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def autorizar_pagamento(request):
    if request.method == 'POST':
        if not request.user.has_perm('processos.pode_autorizar_pagamento'):
            raise PermissionDenied
        selecionados = request.POST.getlist('processos_selecionados')

        if selecionados:
            status_autorizado, _ = StatusChoicesProcesso.objects.get_or_create(
                status_choice__iexact='A PAGAR - AUTORIZADO',
                defaults={'status_choice': 'A PAGAR - AUTORIZADO'}
            )

            Processo.objects.filter(id__in=selecionados).update(status=status_autorizado)
            messages.success(request, f'{len(selecionados)} pagamento(s) autorizado(s) com sucesso!')
        else:
            messages.warning(request, 'Nenhum processo foi selecionado para autorização.')

    return redirect('painel_autorizacao')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def recusar_autorizacao_view(request, pk):
    processo = get_object_or_404(Processo, id=pk)

    if request.method == 'POST':
        if not request.user.has_perm('processos.pode_autorizar_pagamento'):
            raise PermissionDenied
        form = PendenciaForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                pendencia = form.save(commit=False)
                pendencia.processo = processo

                status_pendencia, _ = StatusChoicesPendencias.objects.get_or_create(
                    status_choice__iexact='A RESOLVER', defaults={'status_choice': 'A RESOLVER'}
                )
                pendencia.status = status_pendencia
                pendencia.save()

                status_devolvido, _ = StatusChoicesProcesso.objects.get_or_create(
                    status_choice__iexact='AGUARDANDO LIQUIDAÇÃO / ATESTE',
                    defaults={'status_choice': 'AGUARDANDO LIQUIDAÇÃO / ATESTE'}
                )
                processo.status = status_devolvido
                processo.save()

            messages.error(request, f'Processo #{processo.id} não autorizado e devolvido com pendência!')
        else:
            messages.warning(request, 'Erro ao registrar recusa. Verifique os dados da pendência.')

    return redirect('painel_autorizacao')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def painel_conferencia_view(request):
    processos_pagos = Processo.objects.filter(
        status__status_choice__iexact='PAGO - EM CONFERÊNCIA'
    ).annotate(
        tem_pendencia=Exists(
            Pendencia.objects.filter(
                processo=OuterRef('pk')
            ).exclude(status__status_choice__iexact='RESOLVIDO')
        ),
        tem_retencao=Exists(
            RetencaoImposto.objects.filter(
                nota_fiscal__processo=OuterRef('pk')
            ).exclude(status__status_choice__iexact='PAGO')
        )
    ).order_by('data_pagamento')

    FILTROS_VALIDOS = {'com_pendencia', 'com_retencao', 'com_ambos', 'sem_pendencias'}
    filtro = request.GET.get('filtro', '')
    if filtro not in FILTROS_VALIDOS:
        filtro = ''
    if filtro == 'com_pendencia':
        processos_pagos = processos_pagos.filter(tem_pendencia=True)
    elif filtro == 'com_retencao':
        processos_pagos = processos_pagos.filter(tem_retencao=True)
    elif filtro == 'com_ambos':
        processos_pagos = processos_pagos.filter(tem_pendencia=True, tem_retencao=True)
    elif filtro == 'sem_pendencias':
        processos_pagos = processos_pagos.filter(tem_pendencia=False, tem_retencao=False)

    context = {
        'processos': processos_pagos,
        'pode_interagir': request.user.has_perm('processos.pode_operar_contas_pagar'),
        'filtro_ativo': filtro,
    }
    return render(request, 'fluxo/conferencia.html', context)


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def aprovar_conferencia_view(request, pk):
    messages.error(request, 'A aprovação direta foi desativada. Abra o processo para realizar a conferência.')
    return redirect('painel_conferencia')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def iniciar_conferencia_view(request):
    """POST: store selected process IDs in session queue, redirect to first process."""
    if request.method == 'POST':
        if not request.user.has_perm('processos.pode_operar_contas_pagar'):
            raise PermissionDenied
        ids_raw = request.POST.getlist('processo_ids')
        process_ids = []
        for pid in ids_raw:
            try:
                process_ids.append(int(pid))
            except (ValueError, TypeError):
                pass

        if not process_ids:
            messages.warning(request, 'Selecione ao menos um processo para iniciar a conferência.')
            return redirect('painel_conferencia')

        request.session['conferencia_queue'] = process_ids
        request.session.modified = True
        return redirect('conferencia_processo', pk=process_ids[0])

    return redirect('painel_conferencia')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def conferencia_processo_view(request, pk):
    """Detailed conferência view for reviewing a single process."""
    HISTORY_TYPE_LABELS = {'+': 'Criação', '~': 'Alteração', '-': 'Exclusão'}

    processo = get_object_or_404(Processo, id=pk)

    # Navigation queue
    queue = request.session.get('conferencia_queue', [])
    current_index = queue.index(pk) if pk in queue else -1
    next_pk = queue[current_index + 1] if 0 <= current_index < len(queue) - 1 else None
    prev_pk = queue[current_index - 1] if current_index > 0 else None

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'sair':
            request.session.pop('conferencia_queue', None)
            request.session.modified = True
            return redirect('painel_conferencia')

        if action == 'pular':
            if next_pk:
                return redirect('conferencia_processo', pk=next_pk)
            messages.info(request, 'Não há mais processos na fila. Retornando ao painel.')
            request.session.pop('conferencia_queue', None)
            request.session.modified = True
            return redirect('painel_conferencia')

        if action == 'voltar':
            if prev_pk:
                return redirect('conferencia_processo', pk=prev_pk)
            messages.info(request, 'Não há processo anterior na fila.')
            return redirect('conferencia_processo', pk=pk)

        if action in ('confirmar', 'salvar'):
            if not request.user.has_perm('processos.pode_operar_contas_pagar'):
                raise PermissionDenied
            doc_formset = DocumentoFormSet(
                request.POST, request.FILES,
                instance=processo,
                prefix='documentos',
            )
            pendencia_formset = PendenciaFormSet(
                request.POST,
                instance=processo,
                prefix='pendencias',
            )

            if doc_formset.is_valid() and pendencia_formset.is_valid():
                with transaction.atomic():
                    # Save documents; never delete existing ones
                    for form in doc_formset.forms:
                        if not form.cleaned_data:
                            continue
                        should_delete = form.cleaned_data.get('DELETE', False)
                        is_existing = bool(form.instance.pk)
                        if should_delete and is_existing:
                            # Existing documents are protected from deletion in conferência
                            continue
                        if should_delete and not is_existing:
                            continue
                        if form.has_changed() or not is_existing:
                            instance = form.save(commit=False)
                            instance.processo = processo
                            instance.save()

                    # Mark every document on this process as immutable
                    processo.documentos.all().update(imutavel=True)

                    # Save pendências
                    pendencia_formset.save()

                    if action == 'confirmar':
                        status_contabilizar, _ = StatusChoicesProcesso.objects.get_or_create(
                            status_choice__iexact='PAGO - A CONTABILIZAR',
                            defaults={'status_choice': 'PAGO - A CONTABILIZAR'}
                        )
                        processo.status = status_contabilizar
                        processo.save()
                        messages.success(
                            request,
                            f'Processo #{processo.id} confirmado na conferência e enviado para Contabilização!'
                        )
                        if next_pk:
                            return redirect('conferencia_processo', pk=next_pk)
                        request.session.pop('conferencia_queue', None)
                        request.session.modified = True
                        return redirect('painel_conferencia')
                    else:
                        messages.success(request, f'Alterações do Processo #{processo.id} salvas.')
                        return redirect('conferencia_processo', pk=pk)
            else:
                messages.error(request, 'Verifique os erros no formulário abaixo.')

    # ── GET (or failed POST) ──────────────────────────────────────────────
    doc_formset = DocumentoFormSet(instance=processo, prefix='documentos')
    pendencia_formset = PendenciaFormSet(instance=processo, prefix='pendencias')
    pendencia_form = PendenciaForm()

    # Build unified history from all related models
    history_records = []

    for record in processo.history.all().select_related('history_user'):
        history_records.append({
            'modelo': 'Processo',
            'history_date': record.history_date,
            'history_user': record.history_user,
            'history_type': record.history_type,
            'history_type_label': HISTORY_TYPE_LABELS.get(record.history_type, record.history_type),
            'str_repr': str(record),
        })

    for record in DocumentoProcesso.history.filter(processo_id=pk).select_related('history_user'):
        history_records.append({
            'modelo': 'Documento',
            'history_date': record.history_date,
            'history_user': record.history_user,
            'history_type': record.history_type,
            'history_type_label': HISTORY_TYPE_LABELS.get(record.history_type, record.history_type),
            'str_repr': str(record),
        })

    for record in Pendencia.history.filter(processo_id=pk).select_related('history_user'):
        history_records.append({
            'modelo': 'Pendência',
            'history_date': record.history_date,
            'history_user': record.history_user,
            'history_type': record.history_type,
            'history_type_label': HISTORY_TYPE_LABELS.get(record.history_type, record.history_type),
            'str_repr': str(record),
        })

    for record in DocumentoFiscal.history.filter(processo_id=pk).select_related('history_user'):
        history_records.append({
            'modelo': 'Nota Fiscal',
            'history_date': record.history_date,
            'history_user': record.history_user,
            'history_type': record.history_type,
            'history_type_label': HISTORY_TYPE_LABELS.get(record.history_type, record.history_type),
            'str_repr': str(record),
        })

    history_records.sort(key=lambda x: x['history_date'], reverse=True)

    context = {
        'processo': processo,
        'doc_formset': doc_formset,
        'pendencia_formset': pendencia_formset,
        'pendencia_form': pendencia_form,
        'history_records': history_records,
        'queue': queue,
        'current_index': current_index,
        'next_pk': next_pk,
        'prev_pk': prev_pk,
        'queue_length': len(queue),
        'queue_position': current_index + 1 if current_index >= 0 else 1,
        'tipos_documento': TiposDeDocumento.objects.all(),
        'pode_interagir': request.user.has_perm('processos.pode_operar_contas_pagar'),
    }
    return render(request, 'fluxo/conferencia_processo.html', context)


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def painel_contabilizacao_view(request):
    processos = Processo.objects.filter(status__status_choice__iexact='PAGO - A CONTABILIZAR').order_by('data_pagamento')
    context = {
        'processos': processos,
        'pendencia_form': PendenciaForm(),
        'pode_interagir': request.user.has_perm('processos.pode_contabilizar'),
    }

    return render(request, 'fluxo/contabilizacao.html', context)


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def iniciar_contabilizacao_view(request):
    """POST: store selected process IDs in session queue, redirect to first process."""
    if request.method == 'POST':
        if not request.user.has_perm('processos.pode_contabilizar'):
            raise PermissionDenied
        ids_raw = request.POST.getlist('processo_ids')
        process_ids = []
        for pid in ids_raw:
            try:
                process_ids.append(int(pid))
            except (ValueError, TypeError):
                pass

        if not process_ids:
            messages.warning(request, 'Selecione ao menos um processo para iniciar a contabilização.')
            return redirect('painel_contabilizacao')

        request.session['contabilizacao_queue'] = process_ids
        request.session.modified = True
        return redirect('contabilizacao_processo', pk=process_ids[0])

    return redirect('painel_contabilizacao')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def contabilizacao_processo_view(request, pk):
    """Detailed contabilização view for reviewing a single process."""
    HISTORY_TYPE_LABELS = {'+': 'Criação', '~': 'Alteração', '-': 'Exclusão'}

    processo = get_object_or_404(Processo, id=pk)

    # Navigation queue
    queue = request.session.get('contabilizacao_queue', [])
    current_index = queue.index(pk) if pk in queue else -1
    next_pk = queue[current_index + 1] if 0 <= current_index < len(queue) - 1 else None
    prev_pk = queue[current_index - 1] if current_index > 0 else None

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'sair':
            request.session.pop('contabilizacao_queue', None)
            request.session.modified = True
            return redirect('painel_contabilizacao')

        if action == 'pular':
            if next_pk:
                return redirect('contabilizacao_processo', pk=next_pk)
            messages.info(request, 'Não há mais processos na fila. Retornando ao painel.')
            request.session.pop('contabilizacao_queue', None)
            request.session.modified = True
            return redirect('painel_contabilizacao')

        if action == 'voltar':
            if prev_pk:
                return redirect('contabilizacao_processo', pk=prev_pk)
            messages.info(request, 'Não há processo anterior na fila.')
            return redirect('contabilizacao_processo', pk=pk)

        if action in ('aprovar', 'rejeitar', 'salvar'):
            if not request.user.has_perm('processos.pode_contabilizar'):
                raise PermissionDenied

            if action == 'rejeitar':
                form = PendenciaForm(request.POST)
                if form.is_valid():
                    with transaction.atomic():
                        pendencia = form.save(commit=False)
                        pendencia.processo = processo
                        status_pendencia, _ = StatusChoicesPendencias.objects.get_or_create(
                            status_choice__iexact='A RESOLVER', defaults={'status_choice': 'A RESOLVER'}
                        )
                        pendencia.status = status_pendencia
                        pendencia.save()

                        status_devolvido, _ = StatusChoicesProcesso.objects.get_or_create(
                            status_choice__iexact='PAGO - EM CONFERÊNCIA',
                            defaults={'status_choice': 'PAGO - EM CONFERÊNCIA'}
                        )
                        processo.status = status_devolvido
                        processo.save()

                    messages.error(
                        request,
                        f'Processo #{processo.id} recusado pela Contabilidade e devolvido para a Conferência!'
                    )
                    if next_pk:
                        return redirect('contabilizacao_processo', pk=next_pk)
                    request.session.pop('contabilizacao_queue', None)
                    request.session.modified = True
                    return redirect('painel_contabilizacao')
                else:
                    messages.warning(request, 'Erro ao registrar recusa. Verifique os dados da pendência.')
                    return redirect('contabilizacao_processo', pk=pk)

            doc_formset = DocumentoFormSet(
                request.POST, request.FILES,
                instance=processo,
                prefix='documentos',
            )
            pendencia_formset = PendenciaFormSet(
                request.POST,
                instance=processo,
                prefix='pendencias',
            )

            if doc_formset.is_valid() and pendencia_formset.is_valid():
                with transaction.atomic():
                    for form in doc_formset.forms:
                        if not form.cleaned_data:
                            continue
                        should_delete = form.cleaned_data.get('DELETE', False)
                        is_existing = bool(form.instance.pk)
                        if should_delete and is_existing:
                            # Documents already marked imutável from conferência are protected
                            continue
                        if should_delete and not is_existing:
                            continue
                        if form.has_changed() or not is_existing:
                            instance = form.save(commit=False)
                            instance.processo = processo
                            instance.save()

                    pendencia_formset.save()

                    if action == 'aprovar':
                        status_conselho, _ = StatusChoicesProcesso.objects.get_or_create(
                            status_choice__iexact='CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL',
                            defaults={'status_choice': 'CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL'}
                        )
                        processo.status = status_conselho
                        processo.save()
                        messages.success(
                            request,
                            f'Processo #{processo.id} contabilizado e enviado ao Conselho Fiscal!'
                        )
                        if next_pk:
                            return redirect('contabilizacao_processo', pk=next_pk)
                        request.session.pop('contabilizacao_queue', None)
                        request.session.modified = True
                        return redirect('painel_contabilizacao')
                    else:
                        messages.success(request, f'Alterações do Processo #{processo.id} salvas.')
                        return redirect('contabilizacao_processo', pk=pk)
            else:
                messages.error(request, 'Verifique os erros no formulário abaixo.')

    # ── GET (or failed POST) ──────────────────────────────────────────────
    doc_formset = DocumentoFormSet(instance=processo, prefix='documentos')
    pendencia_formset = PendenciaFormSet(instance=processo, prefix='pendencias')
    pendencia_form = PendenciaForm()

    history_records = []

    for record in processo.history.all().select_related('history_user'):
        history_records.append({
            'modelo': 'Processo',
            'history_date': record.history_date,
            'history_user': record.history_user,
            'history_type': record.history_type,
            'history_type_label': HISTORY_TYPE_LABELS.get(record.history_type, record.history_type),
            'str_repr': str(record),
        })

    for record in DocumentoProcesso.history.filter(processo_id=pk).select_related('history_user'):
        history_records.append({
            'modelo': 'Documento',
            'history_date': record.history_date,
            'history_user': record.history_user,
            'history_type': record.history_type,
            'history_type_label': HISTORY_TYPE_LABELS.get(record.history_type, record.history_type),
            'str_repr': str(record),
        })

    for record in Pendencia.history.filter(processo_id=pk).select_related('history_user'):
        history_records.append({
            'modelo': 'Pendência',
            'history_date': record.history_date,
            'history_user': record.history_user,
            'history_type': record.history_type,
            'history_type_label': HISTORY_TYPE_LABELS.get(record.history_type, record.history_type),
            'str_repr': str(record),
        })

    for record in DocumentoFiscal.history.filter(processo_id=pk).select_related('history_user'):
        history_records.append({
            'modelo': 'Nota Fiscal',
            'history_date': record.history_date,
            'history_user': record.history_user,
            'history_type': record.history_type,
            'history_type_label': HISTORY_TYPE_LABELS.get(record.history_type, record.history_type),
            'str_repr': str(record),
        })

    history_records.sort(key=lambda x: x['history_date'], reverse=True)

    context = {
        'processo': processo,
        'doc_formset': doc_formset,
        'pendencia_formset': pendencia_formset,
        'pendencia_form': pendencia_form,
        'history_records': history_records,
        'queue': queue,
        'current_index': current_index,
        'next_pk': next_pk,
        'prev_pk': prev_pk,
        'queue_length': len(queue),
        'queue_position': current_index + 1 if current_index >= 0 else 1,
        'tipos_documento': TiposDeDocumento.objects.all(),
        'pode_interagir': request.user.has_perm('processos.pode_contabilizar'),
    }
    return render(request, 'fluxo/contabilizacao_processo.html', context)


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def aprovar_contabilizacao_view(request, pk):
    if request.method == 'POST':
        if not request.user.has_perm('processos.pode_contabilizar'):
            raise PermissionDenied
        processo = get_object_or_404(Processo, id=pk)
        status_conselho, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact='CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL',
            defaults={'status_choice': 'CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL'}
        )
        processo.status = status_conselho
        processo.save()
        messages.success(request, f'Processo #{processo.id} contabilizado e enviado ao Conselho Fiscal!')
    return redirect('painel_contabilizacao')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def recusar_contabilizacao_view(request, pk):
    processo = get_object_or_404(Processo, id=pk)

    if request.method == 'POST':
        if not request.user.has_perm('processos.pode_contabilizar'):
            raise PermissionDenied
        form = PendenciaForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                pendencia = form.save(commit=False)
                pendencia.processo = processo

                status_pendencia, _ = StatusChoicesPendencias.objects.get_or_create(
                    status_choice__iexact='A RESOLVER', defaults={'status_choice': 'A RESOLVER'}
                )
                pendencia.status = status_pendencia
                pendencia.save()

                status_devolvido, _ = StatusChoicesProcesso.objects.get_or_create(
                    status_choice__iexact='PAGO - EM CONFERÊNCIA',
                    defaults={'status_choice': 'PAGO - EM CONFERÊNCIA'}
                )
                processo.status = status_devolvido
                processo.save()

            messages.error(request, f'Processo #{processo.id} recusado pela Contabilidade e devolvido para a Conferência!')
        else:
            messages.warning(request, 'Erro ao registrar recusa. Verifique os dados da pendência.')

    return redirect('painel_contabilizacao')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def painel_conselho_view(request):
    processos = Processo.objects.filter(status__status_choice__iexact='CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL').order_by('data_pagamento')
    context = {
        'processos': processos,
        'pendencia_form': PendenciaForm(),
        'pode_interagir': request.user.has_perm('processos.pode_auditar_conselho'),
    }
    return render(request, 'fluxo/conselho.html', context)


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def iniciar_conselho_view(request):
    """POST: store selected process IDs in session queue, redirect to first process."""
    if request.method == 'POST':
        if not request.user.has_perm('processos.pode_auditar_conselho'):
            raise PermissionDenied
        ids_raw = request.POST.getlist('processo_ids')
        process_ids = []
        for pid in ids_raw:
            try:
                process_ids.append(int(pid))
            except (ValueError, TypeError):
                pass

        if not process_ids:
            messages.warning(request, 'Selecione ao menos um processo para iniciar a revisão.')
            return redirect('painel_conselho')

        request.session['conselho_queue'] = process_ids
        request.session.modified = True
        return redirect('conselho_processo', pk=process_ids[0])

    return redirect('painel_conselho')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def conselho_processo_view(request, pk):
    """Completely readonly view for Conselho Fiscal — can only approve or reject."""
    HISTORY_TYPE_LABELS = {'+': 'Criação', '~': 'Alteração', '-': 'Exclusão'}

    processo = get_object_or_404(Processo, id=pk)

    # Navigation queue
    queue = request.session.get('conselho_queue', [])
    current_index = queue.index(pk) if pk in queue else -1
    next_pk = queue[current_index + 1] if 0 <= current_index < len(queue) - 1 else None
    prev_pk = queue[current_index - 1] if current_index > 0 else None

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'sair':
            request.session.pop('conselho_queue', None)
            request.session.modified = True
            return redirect('painel_conselho')

        if action == 'pular':
            if next_pk:
                return redirect('conselho_processo', pk=next_pk)
            messages.info(request, 'Não há mais processos na fila. Retornando ao painel.')
            request.session.pop('conselho_queue', None)
            request.session.modified = True
            return redirect('painel_conselho')

        if action == 'voltar':
            if prev_pk:
                return redirect('conselho_processo', pk=prev_pk)
            messages.info(request, 'Não há processo anterior na fila.')
            return redirect('conselho_processo', pk=pk)

        if action in ('aprovar', 'rejeitar'):
            if not request.user.has_perm('processos.pode_auditar_conselho'):
                raise PermissionDenied

            if action == 'aprovar':
                status_arquivamento, _ = StatusChoicesProcesso.objects.get_or_create(
                    status_choice__iexact='APROVADO POR CONSELHO FISCAL - PARA ARQUIVAMENTO',
                    defaults={'status_choice': 'APROVADO POR CONSELHO FISCAL - PARA ARQUIVAMENTO'}
                )
                processo.status = status_arquivamento
                processo.save()
                messages.success(
                    request,
                    f'Processo #{processo.id} aprovado pelo Conselho e liberado para arquivamento!'
                )
                if next_pk:
                    return redirect('conselho_processo', pk=next_pk)
                request.session.pop('conselho_queue', None)
                request.session.modified = True
                return redirect('painel_conselho')

            if action == 'rejeitar':
                form = PendenciaForm(request.POST)
                if form.is_valid():
                    with transaction.atomic():
                        pendencia = form.save(commit=False)
                        pendencia.processo = processo
                        status_pendencia, _ = StatusChoicesPendencias.objects.get_or_create(
                            status_choice__iexact='A RESOLVER', defaults={'status_choice': 'A RESOLVER'}
                        )
                        pendencia.status = status_pendencia
                        pendencia.save()

                        status_devolvido, _ = StatusChoicesProcesso.objects.get_or_create(
                            status_choice__iexact='PAGO - A CONTABILIZAR',
                            defaults={'status_choice': 'PAGO - A CONTABILIZAR'}
                        )
                        processo.status = status_devolvido
                        processo.save()

                    messages.error(
                        request,
                        f'Processo #{processo.id} recusado pelo Conselho Fiscal e devolvido para a Contabilidade!'
                    )
                    if next_pk:
                        return redirect('conselho_processo', pk=next_pk)
                    request.session.pop('conselho_queue', None)
                    request.session.modified = True
                    return redirect('painel_conselho')
                else:
                    messages.warning(request, 'Erro ao registrar recusa. Verifique os dados da pendência.')
                    return redirect('conselho_processo', pk=pk)

    # ── GET (or failed POST) ──────────────────────────────────────────────
    pendencia_form = PendenciaForm()

    history_records = []

    for record in processo.history.all().select_related('history_user'):
        history_records.append({
            'modelo': 'Processo',
            'history_date': record.history_date,
            'history_user': record.history_user,
            'history_type': record.history_type,
            'history_type_label': HISTORY_TYPE_LABELS.get(record.history_type, record.history_type),
            'str_repr': str(record),
        })

    for record in DocumentoProcesso.history.filter(processo_id=pk).select_related('history_user'):
        history_records.append({
            'modelo': 'Documento',
            'history_date': record.history_date,
            'history_user': record.history_user,
            'history_type': record.history_type,
            'history_type_label': HISTORY_TYPE_LABELS.get(record.history_type, record.history_type),
            'str_repr': str(record),
        })

    for record in Pendencia.history.filter(processo_id=pk).select_related('history_user'):
        history_records.append({
            'modelo': 'Pendência',
            'history_date': record.history_date,
            'history_user': record.history_user,
            'history_type': record.history_type,
            'history_type_label': HISTORY_TYPE_LABELS.get(record.history_type, record.history_type),
            'str_repr': str(record),
        })

    for record in DocumentoFiscal.history.filter(processo_id=pk).select_related('history_user'):
        history_records.append({
            'modelo': 'Nota Fiscal',
            'history_date': record.history_date,
            'history_user': record.history_user,
            'history_type': record.history_type,
            'history_type_label': HISTORY_TYPE_LABELS.get(record.history_type, record.history_type),
            'str_repr': str(record),
        })

    history_records.sort(key=lambda x: x['history_date'], reverse=True)

    context = {
        'processo': processo,
        'pendencia_form': pendencia_form,
        'history_records': history_records,
        'queue': queue,
        'current_index': current_index,
        'next_pk': next_pk,
        'prev_pk': prev_pk,
        'queue_length': len(queue),
        'queue_position': current_index + 1 if current_index >= 0 else 1,
        'pode_interagir': request.user.has_perm('processos.pode_auditar_conselho'),
    }
    return render(request, 'fluxo/conselho_processo.html', context)


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def aprovar_conselho_view(request, pk):
    if request.method == 'POST':
        if not request.user.has_perm('processos.pode_auditar_conselho'):
            raise PermissionDenied
        processo = get_object_or_404(Processo, id=pk)
        status_arquivamento, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact='APROVADO POR CONSELHO FISCAL - PARA ARQUIVAMENTO',
            defaults={'status_choice': 'APROVADO POR CONSELHO FISCAL - PARA ARQUIVAMENTO'}
        )
        processo.status = status_arquivamento
        processo.save()
        messages.success(request, f'Processo #{processo.id} aprovado pelo Conselho e liberado para arquivamento!')
    return redirect('painel_conselho')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def recusar_conselho_view(request, pk):
    processo = get_object_or_404(Processo, id=pk)

    if request.method == 'POST':
        if not request.user.has_perm('processos.pode_auditar_conselho'):
            raise PermissionDenied
        form = PendenciaForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                pendencia = form.save(commit=False)
                pendencia.processo = processo

                status_pendencia, _ = StatusChoicesPendencias.objects.get_or_create(
                    status_choice__iexact='A RESOLVER', defaults={'status_choice': 'A RESOLVER'}
                )
                pendencia.status = status_pendencia
                pendencia.save()

                status_devolvido, _ = StatusChoicesProcesso.objects.get_or_create(
                    status_choice__iexact='PAGO - A CONTABILIZAR',
                    defaults={'status_choice': 'PAGO - A CONTABILIZAR'}
                )
                processo.status = status_devolvido
                processo.save()

            messages.error(request, f'Processo #{processo.id} recusado pelo Conselho Fiscal e devolvido para a Contabilidade!')
        else:
            messages.warning(request, 'Erro ao registrar recusa. Verifique os dados da pendência.')

    return redirect('painel_conselho')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def painel_arquivamento_view(request):
    processos_pendentes = Processo.objects.filter(
        status__status_choice__iexact='APROVADO POR CONSELHO FISCAL - PARA ARQUIVAMENTO'
    ).order_by('data_pagamento')

    processos_arquivados = Processo.objects.filter(
        status__status_choice__iexact='ARQUIVADO'
    ).order_by('-id')

    return render(request, 'fluxo/arquivamento.html', {
        'processos_pendentes': processos_pendentes,
        'processos_arquivados': processos_arquivados,
        'pode_interagir': False,
    })


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def arquivar_processo_view(request, pk):
    if request.method == 'POST':
        raise PermissionDenied
    return redirect('painel_arquivamento')


def api_tipos_documento_por_pagamento(request):
    tipo_pagamento_id = request.GET.get('tipo_pagamento_id')

    if not tipo_pagamento_id:
        return JsonResponse({'sucesso': False, 'erro': 'ID não fornecido'})

    try:
        documentos_validos = TiposDeDocumento.objects.filter(
            tipo_de_pagamento_id=tipo_pagamento_id,
            is_active=True
        ).values('id', 'tipo_de_documento').order_by('tipo_de_documento')

        lista_docs = list(documentos_validos)
        return JsonResponse({'sucesso': True, 'tipos': lista_docs})
    except Exception as e:
        return JsonResponse({'sucesso': False, 'erro': str(e)})


def painel_pendencias_view(request):
    queryset_base = Pendencia.objects.select_related(
        'processo', 'status', 'tipo', 'processo__credor', 'processo__status'
    ).all().order_by('-id')

    meu_filtro = PendenciaFilter(request.GET, queryset=queryset_base)

    context = {
        'meu_filtro': meu_filtro,
        'pendencias': meu_filtro.qs,
    }
    return render(request, 'fluxo/painel_pendencias.html', context)

def gerar_dummy_pdf_view(request, pk):
    """Generates a simple dummy PDF and attaches it as a 'NOTA FISCAL (NF)' document
    to the processo, so the triagem page can be accessed and tested immediately."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas
    from django.utils import timezone as tz

    processo = get_object_or_404(Processo, id=pk)

    tipo_nf = TiposDeDocumento.objects.filter(tipo_de_documento__iexact='NOTA FISCAL (NF)').first()
    if not tipo_nf:
        tipo_nf = TiposDeDocumento.objects.create(tipo_de_documento='NOTA FISCAL (NF)')

    buffer = io.BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 80, "NOTA FISCAL DE TESTE")
    c.setFont("Helvetica", 13)
    c.drawCentredString(width / 2, height - 110, "*** DOCUMENTO FICTÍCIO GERADO PARA TESTES ***")
    c.line(50, height - 125, width - 50, height - 125)

    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, height - 160, f"Processo Nº:  {processo.id}")
    c.drawString(60, height - 185, f"Credor:       {processo.credor}")
    c.drawString(60, height - 210, f"Valor Bruto:  R$ {processo.valor_bruto:,.2f}" if processo.valor_bruto else "Valor Bruto:  ---")
    c.drawString(60, height - 235, f"Gerado em:    {tz.now().strftime('%d/%m/%Y %H:%M')}")

    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width / 2, 40, "Este documento é fictício e destina-se exclusivamente a testes do sistema.")
    c.save()
    buffer.seek(0)

    timestamp = tz.now().strftime('%Y%m%d_%H%M%S')
    filename = f'nota_fiscal_dummy_{timestamp}.pdf'
    ordem = processo.documentos.count() + 1

    doc = DocumentoProcesso(processo=processo, tipo=tipo_nf, ordem=ordem)
    doc.arquivo.save(filename, ContentFile(buffer.getvalue()), save=True)

    messages.success(request, f'PDF de teste gerado e vinculado ao Processo #{processo.id}.')
    return redirect('documentos_fiscais', pk=pk)


# Adicione no final do views.py
def api_detalhes_pagamento(request):
    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            processo_ids = dados.get('ids', [])

            # Puxa os processos com os relacionamentos para otimizar a query
            processos = Processo.objects.filter(id__in=processo_ids).select_related('forma_pagamento', 'conta', 'credor').prefetch_related('documentos')

            resultados = []
            for p in processos:
                forma = p.forma_pagamento.forma_de_pagamento.lower() if p.forma_pagamento else ''

                detalhe_tipo = "Não Especificado"
                detalhe_valor = "Verifique o processo"
                codigos_barras = None

                # LÓGICA DE EXIBIÇÃO BASEADA NA FORMA DE PAGAMENTO
                if 'boleto' in forma or 'gerenciador' in forma:
                    detalhe_tipo = "Código de Barras"
                    # Coleta os códigos de barras de todos os documentos vinculados ao processo
                    codigos_barras = [
                        doc.codigo_barras
                        for doc in p.documentos.all()
                        if doc.codigo_barras
                    ]
                    # detalhe_valor mantém o primeiro código apenas como fallback para outros contextos;
                    # o front-end usa codigos_barras para exibir todos os códigos individualmente.
                    detalhe_valor = codigos_barras[0] if codigos_barras else "Não preenchido"

                elif 'pix' in forma:
                    detalhe_tipo = "Chave PIX"
                    detalhe_valor = p.credor.chave_pix if (p.credor and p.credor.chave_pix) else "Credor sem PIX cadastrado"

                elif 'transfer' in forma: # Pega transferência, transferencia, etc.
                    detalhe_tipo = "Conta Bancária"
                    if p.conta:
                        detalhe_valor = f"Banco: {p.conta.banco} | Ag: {p.conta.agencia} | CC: {p.conta.conta}"
                    else:
                        detalhe_valor = "Nenhuma conta vinculada a este processo"

                # ========================================================
                # CORREÇÃO: PROTEÇÃO CONTRA "INVALID FORMAT STRING"
                # ========================================================
                try:
                    # Força a conversão para float para evitar que strings quebrem o f-string
                    valor_num = float(p.valor_liquido) if p.valor_liquido else 0.0
                    # Formata padrão US (1,500.50), depois inverte os sinais para PT-BR (1.500,50)
                    valor_formatado = f"{valor_num:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                except (ValueError, TypeError):
                    valor_formatado = "0,00"

                resultados.append({
                    'id': p.id,
                    'empenho': p.n_nota_empenho or "S/N",
                    'credor': p.credor.nome if p.credor else "Sem Credor",
                    'valor': valor_formatado,
                    'forma': p.forma_pagamento.forma_de_pagamento if p.forma_pagamento else "N/A",
                    'detalhe_tipo': detalhe_tipo,
                    'detalhe_valor': detalhe_valor,
                    'codigos_barras': codigos_barras,
                })

            return JsonResponse({'sucesso': True, 'dados': resultados})
        except Exception as e:
            # Imprime o erro no console do PythonAnywhere para debug
            import traceback
            traceback.print_exc()
            return JsonResponse({'sucesso': False, 'erro': str(e)})

    return JsonResponse({'sucesso': False, 'erro': 'Método inválido'})


def _build_detalhes_pagamento(processos):
    detalhes = []
    totais = {}
    for p in processos:
        forma = p.forma_pagamento.forma_de_pagamento.lower() if p.forma_pagamento else ''
        forma_nome = p.forma_pagamento.forma_de_pagamento if p.forma_pagamento else 'N/A'

        if 'boleto' in forma or 'gerenciador' in forma:
            dados_pagamento = {
                'tipo': 'codigo_barras',
                'codigo_barras': p.codigo_barras or '',
            }
        elif 'pix' in forma:
            dados_pagamento = {
                'tipo': 'pix',
                'chave_pix': (p.credor.chave_pix if p.credor and p.credor.chave_pix else ''),
            }
        elif 'transfer' in forma or 'ted' in forma:
            credor_conta = p.credor.conta if p.credor else None
            dados_pagamento = {
                'tipo': 'transferencia',
                'banco': credor_conta.banco if credor_conta else '',
                'agencia': credor_conta.agencia if credor_conta else '',
                'conta': credor_conta.conta if credor_conta else '',
            }
        else:
            dados_pagamento = {'tipo': 'remessa'}

        detalhes.append({'processo': p, 'dados_pagamento': dados_pagamento})
        valor = p.valor_liquido or 0
        totais[forma_nome] = totais.get(forma_nome, 0) + valor
    return detalhes, totais


def separar_para_lancamento_bancario(request):
    if request.method == 'POST':
        selecionados = request.POST.getlist('processos_selecionados')

        if not selecionados:
            messages.warning(request, 'Nenhum processo foi selecionado.')
            return redirect('contas_a_pagar')

        request.session['processos_lancamento'] = [int(pid) for pid in selecionados]
        return redirect('lancamento_bancario')

    return redirect('contas_a_pagar')


def lancamento_bancario(request):
    ids = request.session.get('processos_lancamento', [])

    if not ids:
        messages.warning(request, 'Nenhum processo foi selecionado.')
        return redirect('contas_a_pagar')

    status_autorizado = StatusChoicesProcesso.objects.filter(
        status_choice__iexact='A PAGAR - AUTORIZADO'
    ).first()
    status_lancado = StatusChoicesProcesso.objects.filter(
        status_choice__iexact='LANÇADO - AGUARDANDO COMPROVANTE'
    ).first()

    processos_qs = Processo.objects.filter(
        id__in=ids
    ).select_related('forma_pagamento', 'conta', 'credor__conta', 'status').order_by('forma_pagamento__forma_de_pagamento', 'id')

    a_pagar_qs = processos_qs.filter(status=status_autorizado) if status_autorizado else processos_qs.none()
    lancados_qs = processos_qs.filter(status=status_lancado) if status_lancado else processos_qs.none()

    processos_a_pagar, totais_a_pagar = _build_detalhes_pagamento(a_pagar_qs)
    processos_lancados, totais_lancados = _build_detalhes_pagamento(lancados_qs)

    totais = {}
    for forma, val in totais_a_pagar.items():
        totais[forma] = totais.get(forma, 0) + val
    for forma, val in totais_lancados.items():
        totais[forma] = totais.get(forma, 0) + val

    context = {
        'processos_a_pagar': processos_a_pagar,
        'processos_lancados': processos_lancados,
        'totais': totais,
    }
    return render(request, 'fluxo/lancamento_bancario.html', context)


def marcar_como_lancado(request):
    if request.method == 'POST':
        processo_id = request.POST.get('processo_id')

        if processo_id:
            status_lancado, _ = StatusChoicesProcesso.objects.get_or_create(
                status_choice__iexact='LANÇADO - AGUARDANDO COMPROVANTE',
                defaults={'status_choice': 'LANÇADO - AGUARDANDO COMPROVANTE'}
            )
            updated = Processo.objects.filter(id=processo_id).update(status=status_lancado)
            if updated:
                messages.success(request, f'Processo #{processo_id} marcado como lançado com sucesso.')
            else:
                messages.warning(request, f'Processo #{processo_id} não encontrado.')
        else:
            messages.warning(request, 'ID de processo inválido.')

    return redirect('lancamento_bancario')


def desmarcar_lancamento(request):
    if request.method == 'POST':
        processo_id = request.POST.get('processo_id')

        if processo_id:
            status_autorizado, _ = StatusChoicesProcesso.objects.get_or_create(
                status_choice__iexact='A PAGAR - AUTORIZADO',
                defaults={'status_choice': 'A PAGAR - AUTORIZADO'}
            )
            updated = Processo.objects.filter(id=processo_id).update(status=status_autorizado)
            if updated:
                messages.success(request, f'Lançamento do Processo #{processo_id} desmarcado.')
            else:
                messages.warning(request, f'Processo #{processo_id} não encontrado.')
        else:
            messages.warning(request, 'ID de processo inválido.')

    return redirect('lancamento_bancario')

from django.views.decorators.http import require_GET

@require_GET
def api_documentos_processo(request, processo_id):
    """Returns a JSON list of documents attached to a Processo, for the iFrame previewer."""
    processo = get_object_or_404(Processo, id=processo_id)
    documentos = processo.documentos.all().order_by('ordem')

    docs_list = []
    for doc in documentos:
        if doc.arquivo:
            nome = doc.arquivo.name.split('/')[-1]
            docs_list.append({
                'id': doc.id,
                'ordem': doc.ordem,
                'tipo': doc.tipo.tipo_de_documento if doc.tipo else 'Documento',
                'nome': nome,
                'url': doc.arquivo.url,
            })

    # Collect pendencias info
    pendencias_qs = processo.pendencias.select_related('status', 'tipo').all()
    pendencias_list = [
        {
            'tipo': str(p.tipo),
            'descricao': p.descricao or '',
            'status': str(p.status) if p.status else '-',
        }
        for p in pendencias_qs
    ]

    # Collect retencoes info (via notas fiscais linked to this processo)
    retencoes_list = []
    for nf in processo.notas_fiscais.prefetch_related('retencoes__status', 'retencoes__codigo').all():
        for ret in nf.retencoes.all():
            retencoes_list.append({
                'codigo': str(ret.codigo),
                'valor': str(ret.valor),
                'status': str(ret.status) if ret.status else '-',
            })

    def fmt_date(d):
        return d.strftime('%d/%m/%Y') if d else '-'

    def fmt_decimal(v):
        if v is None:
            return '-'
        # Format as Brazilian currency: R$ 1.234,56
        int_part, dec_part = f'{abs(v):.2f}'.split('.')
        int_formatted = '{:,}'.format(int(int_part)).replace(',', '.')
        signal = '-' if v < 0 else ''
        return f'R$ {signal}{int_formatted},{dec_part}'

    return JsonResponse({
        'processo_id': processo.id,
        'n_nota_empenho': processo.n_nota_empenho or str(processo.id),
        'credor': str(processo.credor) if processo.credor else '-',
        'valor_bruto': fmt_decimal(processo.valor_bruto),
        'valor_liquido': fmt_decimal(processo.valor_liquido),
        'data_empenho': fmt_date(processo.data_empenho),
        'data_vencimento': fmt_date(processo.data_vencimento),
        'data_pagamento': fmt_date(processo.data_pagamento),
        'status': str(processo.status) if processo.status else '-',
        'pendencias': pendencias_list,
        'retencoes': retencoes_list,
        'documentos': docs_list,
    })


# ==========================================
# AUDITORIA: HISTÓRICO DE ALTERAÇÕES
# ==========================================
def auditoria_view(request):
    HISTORY_TYPE_LABELS = {'+': 'Criação', '~': 'Alteração', '-': 'Exclusão'}

    model_configs = [
        (Processo.history.model, 'Processo'),
        (DocumentoProcesso.history.model, 'Documento de Processo'),
        (DocumentoDiaria.history.model, 'Documento de Diária'),
        (DocumentoReembolso.history.model, 'Documento de Reembolso'),
        (DocumentoJeton.history.model, 'Documento de Jeton'),
        (DocumentoAuxilio.history.model, 'Documento de Auxílio'),
        (DocumentoSuprimentoDeFundos.history.model, 'Documento de Suprimento'),
    ]

    modelo_filter = request.GET.get('modelo', '').strip()
    tipo_filter = request.GET.get('tipo_acao', '').strip()
    data_inicio = request.GET.get('data_inicio', '').strip()
    data_fim = request.GET.get('data_fim', '').strip()
    usuario_filter = request.GET.get('usuario', '').strip()

    all_records = []
    for history_model, label in model_configs:
        if modelo_filter and modelo_filter != label:
            continue
        qs = history_model.objects.select_related('history_user').all()
        if tipo_filter:
            qs = qs.filter(history_type=tipo_filter)
        if data_inicio:
            qs = qs.filter(history_date__date__gte=data_inicio)
        if data_fim:
            qs = qs.filter(history_date__date__lte=data_fim)
        if usuario_filter:
            qs = qs.filter(history_user__username__icontains=usuario_filter)
        for record in qs:
            all_records.append({
                'modelo': label,
                'object_id': record.id,  # original object PK (copied from the tracked model)
                'history_date': record.history_date,
                'history_user': record.history_user,
                'history_type': record.history_type,
                'history_type_label': HISTORY_TYPE_LABELS.get(record.history_type, record.history_type),
                'history_change_reason': getattr(record, 'history_change_reason', None),
                'str_repr': str(record),
            })

    all_records.sort(key=lambda x: x['history_date'], reverse=True)
    total = len(all_records)
    all_records = all_records[:500]

    context = {
        'registros': all_records,
        'total': total,
        'modelos_disponiveis': [label for _, label in model_configs],
        'filtros': {
            'modelo': modelo_filter,
            'tipo_acao': tipo_filter,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'usuario': usuario_filter,
        },
    }
    return render(request, 'fluxo/auditoria.html', context)


def api_processo_detalhes(request):
    """API endpoint that returns Processo details as JSON for the contingency form."""
    processo_id = request.GET.get('id', '').strip()
    if not processo_id:
        return JsonResponse({'sucesso': False, 'erro': 'ID do processo não informado.'}, status=400)

    try:
        processo = Processo.objects.select_related(
            'credor', 'forma_pagamento', 'tipo_pagamento', 'conta', 'status', 'tag'
        ).get(pk=processo_id)
    except Processo.DoesNotExist:
        return JsonResponse({'sucesso': False, 'erro': f'Processo #{processo_id} não encontrado.'}, status=404)
    except ValueError:
        return JsonResponse({'sucesso': False, 'erro': 'ID inválido.'}, status=400)

    dados = {
        'sucesso': True,
        'processo': {
            'id': processo.pk,
            'n_nota_empenho': processo.n_nota_empenho or '—',
            'credor_id': processo.credor_id,
            'credor_nome': str(processo.credor) if processo.credor else '—',
            'data_empenho': str(processo.data_empenho) if processo.data_empenho else None,
            'valor_bruto': str(processo.valor_bruto) if processo.valor_bruto is not None else '0.00',
            'valor_liquido': str(processo.valor_liquido) if processo.valor_liquido is not None else '0.00',
            'ano_exercicio': processo.ano_exercicio,
            'n_pagamento_siscac': processo.n_pagamento_siscac or '—',
            'codigo_barras': processo.codigo_barras or '—',
            'data_vencimento': str(processo.data_vencimento) if processo.data_vencimento else None,
            'data_pagamento': str(processo.data_pagamento) if processo.data_pagamento else None,
            'forma_pagamento': str(processo.forma_pagamento) if processo.forma_pagamento else '—',
            'tipo_pagamento': str(processo.tipo_pagamento) if processo.tipo_pagamento else '—',
            'observacao': processo.observacao or '—',
            'conta': str(processo.conta) if processo.conta else '—',
            'status': str(processo.status) if processo.status else '—',
            'detalhamento': processo.detalhamento or '—',
            'tag': str(processo.tag) if processo.tag else '—',
            'em_contingencia': processo.em_contingencia,
            'extraorcamentario': processo.extraorcamentario,
        }
    }
    return JsonResponse(dados)


def painel_contingencias_view(request):
    """Displays a filterable list of all Contingencias."""
    queryset = Contingencia.objects.select_related('processo', 'solicitante').order_by('-data_solicitacao')
    meu_filtro = ContingenciaFilter(request.GET, queryset=queryset)
    return render(request, 'fluxo/painel_contingencias.html', {
        'filter': meu_filtro,
        'contingencias': meu_filtro.qs,
    })


def add_contingencia_view(request):
    """Renders the form to request an exceptional correction (Contingency) on a locked Processo."""
    if request.method == 'POST':
        processo_id = request.POST.get('processo_id', '').strip()
        justificativa = request.POST.get('justificativa', '').strip()
        dados_propostos_raw = request.POST.get('dados_propostos', '{}').strip()

        if not processo_id or not justificativa:
            messages.error(request, 'Processo e justificativa são obrigatórios.')
            return redirect('add_contingencia')

        try:
            pk = int(processo_id)
        except ValueError:
            messages.error(request, 'Processo não encontrado.')
            return redirect('add_contingencia')

        processo = get_object_or_404(Processo, pk=pk)

        try:
            dados_propostos = json.loads(dados_propostos_raw) if dados_propostos_raw else {}
        except (json.JSONDecodeError, ValueError):
            dados_propostos = {}

        contingencia = Contingencia.objects.create(
            processo=processo,
            solicitante=request.user,
            justificativa=justificativa,
            dados_propostos=dados_propostos,
            status='PENDENTE_SUPERVISOR',
        )
        processo.em_contingencia = True
        processo.save(update_fields=['em_contingencia'])

        messages.success(
            request,
            f'Contingência #{contingencia.pk} aberta com sucesso para o Processo #{processo.pk}. '
            'Aguardando aprovação do Supervisor.'
        )
        return redirect('home_page')

    return render(request, 'fluxo/add_contingencia.html')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.pode_autorizar_pagamento'))
def gerar_autorizacao_pagamento_view(request, pk):
    """
    Gera e serve o PDF "Termo de Autorização de Pagamento" para o processo indicado.
    """
    processo = get_object_or_404(Processo, pk=pk)
    pdf_buffer = gerar_pdf_autorizacao(processo)
    nome_arquivo = f"Autorizacao_Pagamento_Proc_{processo.id}.pdf"
    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nome_arquivo}"'
    return response


@login_required
@user_passes_test(lambda u: u.has_perm('processos.pode_auditar_conselho'))
def gerar_parecer_conselho_view(request, pk):
    """
    Gera e serve o PDF "Parecer do Conselho Fiscal" para o processo indicado.
    """
    processo = get_object_or_404(Processo, pk=pk)
    pdf_buffer = gerar_pdf_conselho_fiscal(processo)
    nome_arquivo = f"Parecer_Conselho_Fiscal_Proc_{processo.id}.pdf"
    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nome_arquivo}"'
    return response


def _ensure_fake_lookup_tables():
    """Create minimal lookup table records required for fake data generation."""
    for s in [
        "AGUARDANDO LIQUIDAÇÃO / ATESTE",
        "A PAGAR - PENDENTE AUTORIZAÇÃO",
        "PAGO - EM CONFERÊNCIA",
        "ARQUIVADO",
        "CANCELADO / ANULADO",
    ]:
        StatusChoicesProcesso.objects.get_or_create(status_choice=s)

    for t in ["Serviços", "Material", "Contrato", "Diárias"]:
        TagChoices.objects.get_or_create(tag_choice=t)

    for f in ["PIX", "TRANSFERÊNCIA (TED)", "REMESSA BANCÁRIA"]:
        FormasDePagamento.objects.get_or_create(forma_de_pagamento=f)

    for t in ["CONTAS FIXAS", "VERBAS INDENIZATÓRIAS", "IMPOSTOS"]:
        TiposDePagamento.objects.get_or_create(tipo_de_pagamento=t)

    for s in ["A RECOLHER", "RECOLHIDA"]:
        StatusChoicesRetencoes.objects.get_or_create(status_choice=s)

    for s in ["PENDENTE", "APROVADO", "CONCLUÍDO"]:
        StatusChoicesVerbasIndenizatorias.objects.get_or_create(status_choice=s)

    for m in ["Veículo Próprio", "Transporte Público", "Aéreo"]:
        MeiosDeTransporte.objects.get_or_create(meio_de_transporte=m)

    grupo_forn, _ = Grupos.objects.get_or_create(grupo="FORNECEDORES")
    grupo_func, _ = Grupos.objects.get_or_create(grupo="FUNCIONÁRIOS")

    for cargo in ["Analista", "Assessor", "Diretor", "Técnico Administrativo"]:
        CargosFuncoes.objects.get_or_create(grupo=grupo_func, cargo_funcao=cargo)
    for cargo in ["Empresa de TI", "Empresa de Limpeza"]:
        CargosFuncoes.objects.get_or_create(grupo=grupo_forn, cargo_funcao=cargo)

    if not ContasBancarias.objects.exists():
        ContasBancarias.objects.create(
            titular=_fake_generator.company(),
            banco="Banco do Brasil",
            agencia="0001",
            conta=str(random.randint(10000, 99999)),
        )

    if not CodigosImposto.objects.exists():
        CodigosImposto.objects.create(
            codigo="1708",
            aliquota=Decimal("1.50"),
            regra_competencia="pagamento",
            serie_reinf="S4000",
        )

    if not Credor.objects.filter(tipo='PJ').exists():
        grupo_forn = Grupos.objects.filter(grupo="FORNECEDORES").first()
        ContasBancarias.objects.get_or_create(
            banco="Caixa Econômica Federal",
            agencia="1234",
            defaults={
                "titular": _fake_generator.company(),
                "conta": str(random.randint(10000, 99999)),
            },
        )
        conta = ContasBancarias.objects.first()
        Credor.objects.create(
            nome=_fake_generator.company(),
            cpf_cnpj=_fake_generator.cnpj(),
            tipo='PJ',
            grupo=grupo_forn,
            conta=conta,
            email=_fake_generator.email(),
            telefone=_fake_generator.phone_number()[:20],
            chave_pix=_fake_generator.email(),
        )

    if not Credor.objects.filter(tipo='PF').exists():
        grupo_func = Grupos.objects.filter(grupo="FUNCIONÁRIOS").first()
        conta = ContasBancarias.objects.first()
        cargo = CargosFuncoes.objects.filter(grupo=grupo_func).first()
        Credor.objects.create(
            nome=_fake_generator.name(),
            cpf_cnpj=_fake_generator.cpf(),
            tipo='PF',
            grupo=grupo_func,
            cargo_funcao=cargo,
            conta=conta,
            email=_fake_generator.email(),
            telefone=_fake_generator.phone_number()[:20],
            chave_pix=_fake_generator.email(),
        )


def _create_fake_processos(n):
    """Create n fake Processo records and return the count created."""
    status_list = list(StatusChoicesProcesso.objects.all())
    tag_list = list(TagChoices.objects.all())
    forma_list = list(FormasDePagamento.objects.all())
    tipo_list = list(TiposDePagamento.objects.all())
    contas = list(ContasBancarias.objects.all())
    credores = list(Credor.objects.all())

    if not credores or not contas or not status_list:
        return 0

    current_year = date.today().year
    created = 0
    for i in range(n):
        data_empenho = _fake_generator.date_between(start_date="-2y", end_date="today")
        data_vencimento = data_empenho + timedelta(days=random.randint(15, 90))
        data_pagamento = data_vencimento + timedelta(days=random.randint(0, 30))
        valor_bruto = Decimal(str(round(random.uniform(500.00, 150_000.00), 2)))
        retencao_pct = Decimal(str(round(random.uniform(0, 0.15), 4)))
        valor_liquido = (valor_bruto * (1 - retencao_pct)).quantize(Decimal("0.01"))
        ano = data_empenho.year if _MIN_FAKE_ANO_EXERCICIO <= data_empenho.year <= current_year else current_year
        existing_count = Processo.objects.count()
        n_empenho = f"{ano}NE{str(existing_count + i + 1).zfill(5)}"
        n_siscac = f"PAG{str(existing_count + i + 1).zfill(6)}"
        Processo.objects.create(
            extraorcamentario=random.choice([False, False, False, True]),
            n_nota_empenho=n_empenho,
            credor=random.choice(credores),
            data_empenho=data_empenho,
            valor_bruto=valor_bruto,
            valor_liquido=valor_liquido,
            ano_exercicio=ano,
            n_pagamento_siscac=n_siscac,
            codigo_barras=_fake_generator.numerify(
                "####.#####  #####.###### #####.###### # ##############"
            ),
            data_vencimento=data_vencimento,
            data_pagamento=data_pagamento,
            forma_pagamento=random.choice(forma_list) if forma_list else None,
            tipo_pagamento=random.choice(tipo_list) if tipo_list else None,
            observacao=_fake_generator.sentence(nb_words=8)[:200],
            conta=random.choice(contas),
            status=random.choice(status_list),
            detalhamento=_fake_generator.sentence(nb_words=10)[:200],
            tag=random.choice(tag_list) if tag_list else None,
        )
        created += 1
    return created


def _create_fake_documentos_fiscais(n, processos):
    """Create n fake DocumentoFiscal records linked to existing processos."""
    credores_pj = list(Credor.objects.filter(tipo='PJ'))
    credores_func = list(Credor.objects.filter(tipo='PF'))
    if not credores_pj:
        credores_pj = list(Credor.objects.all())

    created = 0
    for i in range(n):
        processo = random.choice(processos)
        emitente = random.choice(credores_pj) if credores_pj else None
        fiscal = random.choice(credores_func) if credores_func else None
        data_emissao = _fake_generator.date_between(start_date="-1y", end_date="today")
        valor_bruto = Decimal(str(round(random.uniform(100.00, 50_000.00), 2)))
        retencao_pct = Decimal(str(round(random.uniform(0, 0.15), 4)))
        valor_liquido = (valor_bruto * (1 - retencao_pct)).quantize(Decimal("0.01"))
        DocumentoFiscal.objects.create(
            processo=processo,
            nome_emitente=emitente,
            numero_nota_fiscal=_fake_generator.numerify("NF-#####"),
            serie_nota_fiscal=_fake_generator.numerify("###"),
            data_emissao=data_emissao,
            valor_bruto=valor_bruto,
            valor_liquido=valor_liquido,
            atestada=random.choice([True, False]),
            fiscal_contrato=fiscal,
        )
        created += 1
    return created


def _create_fake_retencoes(n, notas):
    """Create n fake RetencaoImposto records linked to existing DocumentoFiscal records."""
    codigos = list(CodigosImposto.objects.all())
    status_list = list(StatusChoicesRetencoes.objects.all())
    credores = list(Credor.objects.all())

    if not codigos:
        return 0

    created = 0
    for _ in range(n):
        nota = random.choice(notas)
        beneficiario = nota.nome_emitente or (random.choice(credores) if credores else None)
        rendimento = Decimal(str(round(random.uniform(500.00, 30_000.00), 2)))
        codigo = random.choice(codigos)
        aliquota = codigo.aliquota or Decimal("0.015")
        valor = (rendimento * aliquota / 100).quantize(Decimal("0.01"))
        data_pagamento = _fake_generator.date_between(start_date="-1y", end_date="today")
        RetencaoImposto.objects.create(
            nota_fiscal=nota,
            beneficiario=beneficiario,
            codigo=codigo,
            valor=valor,
            rendimento_tributavel=rendimento,
            data_pagamento=data_pagamento,
            status=random.choice(status_list) if status_list else None,
        )
        created += 1
    return created


def _create_fake_diarias(n, credores_pf, processos):
    """Create n fake Diaria records. Links to existing processos when available."""
    status_list = list(StatusChoicesVerbasIndenizatorias.objects.all())
    transportes = list(MeiosDeTransporte.objects.all())

    cidades_origem = ["Brasília/DF", "São Paulo/SP", "Rio de Janeiro/RJ", "Belo Horizonte/MG"]
    cidades_destino = ["Manaus/AM", "Fortaleza/CE", "Salvador/BA", "Recife/PE", "Porto Alegre/RS", "Curitiba/PR"]

    created = 0
    for i in range(n):
        beneficiario = random.choice(credores_pf)
        proponente = random.choice(credores_pf)
        data_saida = _fake_generator.date_between(start_date="-6m", end_date="today")
        dias = random.randint(1, 10)
        data_retorno = data_saida + timedelta(days=dias)
        quantidade = Decimal(str(round(random.uniform(0.5, float(dias)), 1)))
        existing_count = Diaria.objects.count()
        numero_seq = f"DIA{date.today().year}{str(existing_count + i + 1).zfill(5)}"
        processo = random.choice(processos) if processos else None
        Diaria.objects.create(
            processo=processo,
            numero_sequencial=numero_seq,
            beneficiario=beneficiario,
            proponente=proponente,
            tipo_solicitacao=random.choice(['INICIAL', 'PRORROGACAO', 'COMPLEMENTACAO']),
            data_saida=data_saida,
            data_retorno=data_retorno,
            cidade_origem=random.choice(cidades_origem),
            cidade_destino=random.choice(cidades_destino),
            objetivo=_fake_generator.sentence(nb_words=8)[:200],
            quantidade_diarias=quantidade,
            meio_de_transporte=random.choice(transportes) if transportes else None,
            status=random.choice(status_list) if status_list else None,
            autorizada=random.choice([True, False]),
        )
        created += 1
    return created


def gerar_dados_fake_view(request):
    """View to generate fake/sample test data for processes, fiscal documents,
    tax retentions and diarias via a web form."""
    context = {'resultados': None}

    if request.method == 'POST':
        try:
            n_processos = max(0, int(request.POST.get('n_processos') or 0))
            n_documentos = max(0, int(request.POST.get('n_documentos') or 0))
            n_retencoes = max(0, int(request.POST.get('n_retencoes') or 0))
            n_diarias = max(0, int(request.POST.get('n_diarias') or 0))
        except (ValueError, TypeError):
            messages.error(request, "Valores inválidos. Use apenas números inteiros.")
            return redirect('gerar_dados_fake')

        _ensure_fake_lookup_tables()

        resultados = {}

        if n_processos > 0:
            criados = _create_fake_processos(n_processos)
            resultados['processos'] = criados
            if criados:
                messages.success(request, f"✔ {criados} processo(s) criado(s).")
            else:
                messages.warning(request, "Não foi possível criar processos. Verifique se há credores e contas bancárias cadastrados.")

        if n_documentos > 0:
            processos_existentes = list(Processo.objects.all())
            if not processos_existentes:
                messages.warning(request, f"Não há processos cadastrados. Os {n_documentos} documento(s) fiscal(is) não puderam ser gerados. Gere processos primeiro.")
            else:
                criados = _create_fake_documentos_fiscais(n_documentos, processos_existentes)
                resultados['documentos_fiscais'] = criados
                messages.success(request, f"✔ {criados} documento(s) fiscal(is) criado(s).")

        if n_retencoes > 0:
            notas_existentes = list(DocumentoFiscal.objects.all())
            if not notas_existentes:
                messages.warning(request, f"Não há documentos fiscais cadastrados. As {n_retencoes} retenção(ões) não puderam ser geradas. Gere documentos fiscais primeiro.")
            else:
                criados = _create_fake_retencoes(n_retencoes, notas_existentes)
                if criados:
                    resultados['retencoes'] = criados
                    messages.success(request, f"✔ {criados} retenção(ões) criada(s).")
                else:
                    messages.warning(request, "Não foi possível criar retenções. Verifique se há códigos de imposto cadastrados.")

        if n_diarias > 0:
            credores_pf = list(Credor.objects.filter(tipo='PF'))
            if not credores_pf:
                messages.warning(request, f"Não há credores PF cadastrados. As {n_diarias} diária(s) não puderam ser geradas.")
            else:
                processos_existentes = list(Processo.objects.all()) if Processo.objects.exists() else None
                criados = _create_fake_diarias(n_diarias, credores_pf, processos_existentes)
                resultados['diarias'] = criados
                messages.success(request, f"✔ {criados} diária(s) criada(s).")

        context['resultados'] = resultados
        return render(request, 'gerar_dados_fake.html', context)

    return render(request, 'gerar_dados_fake.html', context)
