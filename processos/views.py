import io
import os
import json
import tempfile
from datetime import date, datetime
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
from django.db.models import Count, Q, F, Sum
from pypdf import PdfWriter
from .forms import ProcessoForm, DocumentoFormSet, DocumentoFiscalFormSet, RetencaoFormSet, CredorForm, DiariaForm,ReembolsoForm, JetonForm, AuxilioForm, SuprimentoForm, PendenciaForm, PendenciaFormSet
from .utils import extract_siscac_data, mesclar_pdfs_em_memoria, processar_pdf_boleto, processar_pdf_comprovantes, gerar_termo_auditoria, fatiar_pdf_manual, processar_pdf_comprovantes_ia, gerar_pdf_autorizacao, gerar_pdf_conselho_fiscal
from .ai_utils import extrair_dados_documento, extract_data_with_llm, extrair_codigos_barras_boletos
from .invoice_processor import process_invoice_taxes
from .models import Processo, DocumentoFiscal, StatusChoicesProcesso, Credor, Diaria, ReembolsoCombustivel, Jeton, AuxilioRepresentacao, TiposDeDocumento, DocumentoProcesso, DocumentoDiaria, DocumentoReembolso, DocumentoJeton, DocumentoAuxilio, CodigosImposto, RetencaoImposto, SuprimentoDeFundos, DespesaSuprimento, StatusChoicesPendencias, Pendencia, TiposDePendencias, ComprovanteDePagamento, Tabela_Valores_Unitarios_Verbas_Indenizatorias, DocumentoSuprimentoDeFundos, TiposDePagamento, Contingencia, StatusChoicesVerbasIndenizatorias
from .filters import ProcessoFilter, CredorFilter, DiariaFilter, ReembolsoFilter, JetonFilter, AuxilioFilter, RetencaoProcessoFilter, RetencaoNotaFilter, RetencaoIndividualFilter, PendenciaFilter, DocumentoFiscalFilter, ContingenciaFilter, DiariasAutorizacaoFilter

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

            return render(request, 'add_process.html', {
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
                        return render(request, 'add_process.html', {
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

            return render(request, 'add_process.html', {
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

        return render(request, 'add_process.html', {
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

    # Redirect to the dedicated verbas page when this processo contains verbas indenizatórias
    if (
        Diaria.objects.filter(processo=processo).exists()
        or ReembolsoCombustivel.objects.filter(processo=processo).exists()
        or Jeton.objects.filter(processo=processo).exists()
        or AuxilioRepresentacao.objects.filter(processo=processo).exists()
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
        'documentos_fiscais_url': reverse('documentos_fiscais', kwargs={'pk': processo.id}),
    }

    return render(request, 'editar_processo.html', context)


# ==========================================
# DOCUMENTOS FISCAIS: GERENCIAMENTO DE NOTAS FISCAIS
# ==========================================
def documentos_fiscais_view(request, pk):
    """Manage fiscal documents (Notas Fiscais) for a process."""
    processo = get_object_or_404(Processo, id=pk)
    documentos = processo.documentos.all().order_by('ordem')
    fiscais_contrato = Credor.objects.filter(grupo__grupo='FUNCIONÁRIOS').order_by('nome')
    credores = Credor.objects.all().order_by('nome')
    codigos_imposto = CodigosImposto.objects.all().order_by('codigo')
    source = request.GET.get('source', '')

    context = {
        'processo': processo,
        'documentos': documentos,
        'fiscais_contrato': fiscais_contrato,
        'credores': credores,
        'codigos_imposto': codigos_imposto,
        'source': source,
    }
    return render(request, 'documentos_fiscais.html', context)


def api_toggle_documento_fiscal(request, processo_pk, documento_pk):
    """AJAX: Toggle a document as nota fiscal (create/delete DocumentoFiscal)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    processo = get_object_or_404(Processo, id=processo_pk)
    doc = get_object_or_404(DocumentoProcesso, id=documento_pk, processo=processo)

    try:
        nota = doc.nota_referente
        nota.retencoes.all().delete()
        nota.delete()
        return JsonResponse({'status': 'removed', 'message': 'Documento fiscal removido.'})
    except (DocumentoFiscal.DoesNotExist, AttributeError):
        nota = DocumentoFiscal.objects.create(
            processo=processo,
            documento_vinculado=doc,
            numero_nota_fiscal=f'DOC-{doc.ordem}',
            data_emissao=date.today(),
            valor_bruto=0,
            valor_liquido=0,
        )
        return JsonResponse({
            'status': 'created',
            'nota_id': nota.id,
            'message': 'Documento marcado como fiscal.',
        })


def api_salvar_nota_fiscal(request, processo_pk, nota_pk):
    """AJAX: Save nota fiscal details (retencoes and ateste pendencia)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    processo = get_object_or_404(Processo, id=processo_pk)
    nota = get_object_or_404(DocumentoFiscal, id=nota_pk, processo=processo)

    try:
        body = json.loads(request.body)
    except (ValueError, AttributeError):
        body = request.POST

    emitente_id = body.get('nome_emitente')
    if emitente_id:
        try:
            nota.nome_emitente = Credor.objects.get(id=int(emitente_id))
        except (Credor.DoesNotExist, ValueError, TypeError):
            nota.nome_emitente = None
    else:
        nota.nome_emitente = None

    numero = body.get('numero_nota_fiscal')
    if numero:
        nota.numero_nota_fiscal = numero

    data_str = body.get('data_emissao', '')
    if data_str:
        try:
            nota.data_emissao = datetime.strptime(str(data_str), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass

    vb = body.get('valor_bruto', '')
    if vb:
        try:
            nota.valor_bruto = float(str(vb).replace(',', '.'))
        except (ValueError, TypeError):
            pass

    fiscal_id = body.get('fiscal_contrato')
    if fiscal_id:
        try:
            nota.fiscal_contrato = Credor.objects.get(id=int(fiscal_id))
        except (Credor.DoesNotExist, ValueError, TypeError):
            nota.fiscal_contrato = None
    else:
        nota.fiscal_contrato = None

    atestada = body.get('atestada')
    nota.atestada = bool(atestada) if isinstance(atestada, bool) else str(atestada).lower() in ('true', '1', 'on')

    serie = body.get('serie_nota_fiscal', '')
    nota.serie_nota_fiscal = serie.strip() if serie else None

    codigo_servico = body.get('codigo_servico_inss', '')
    nota.codigo_servico_inss = codigo_servico.strip() if codigo_servico else None

    nota.save()

    nota.retencoes.all().delete()
    codigos = body.get('imposto_codes', [])
    valores = body.get('imposto_values', [])
    rendimentos = body.get('imposto_rendimentos', [])
    beneficiarios = body.get('imposto_beneficiarios', [])
    for c, r, v, b in zip(codigos, rendimentos, valores, beneficiarios):
        if c and v:
            try:
                beneficiario_id = int(b) if b and str(b).strip() else None
            except (ValueError, TypeError):
                beneficiario_id = None
            try:
                rend_val = float(str(r).replace(',', '.')) if r and str(r).strip() else None
                imp_val = float(str(v).replace(',', '.'))
                RetencaoImposto.objects.create(
                    nota_fiscal=nota,
                    codigo_id=c,
                    rendimento_tributavel=rend_val,
                    valor=imp_val,
                    beneficiario_id=beneficiario_id,
                )
            except (ValueError, TypeError) as exc:
                print(f'Erro ao criar retenção: {exc}')

    # Recalculate valor_liquido server-side as valor_bruto minus sum of retencoes
    total_retencoes = nota.retencoes.aggregate(total=Sum('valor'))['total'] or 0
    nota.valor_liquido = (nota.valor_bruto or 0) - total_retencoes
    nota.save(update_fields=['valor_liquido'])

    tipo_pendencia, _ = TiposDePendencias.objects.get_or_create(
        tipo_de_pendencia__iexact='ATESTE DE LIQUIDAÇÃO',
        defaults={'tipo_de_pendencia': 'ATESTE DE LIQUIDAÇÃO'}
    )
    if not nota.atestada:
        status_pendencia, _ = StatusChoicesPendencias.objects.get_or_create(
            status_choice__iexact='A RESOLVER',
            defaults={'status_choice': 'A RESOLVER'}
        )
        if not processo.pendencias.filter(tipo=tipo_pendencia).exists():
            Pendencia.objects.create(
                processo=processo,
                tipo=tipo_pendencia,
                descricao='DOCUMENTO PENDENTE DE ATESTE DE FISCAL DE CONTRATO',
                status=status_pendencia,
            )
    else:
        outras_nao_atestadas = processo.notas_fiscais.filter(atestada=False).exclude(id=nota.id).exists()
        if not outras_nao_atestadas:
            processo.pendencias.filter(tipo=tipo_pendencia).delete()

    return JsonResponse({'status': 'ok', 'message': 'Nota fiscal salva com sucesso.'})


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
    processos_pendentes = Processo.objects.filter(
        status__status_choice__in=[
            'A PAGAR - PENDENTE AUTORIZAÇÃO',
            'A PAGAR - ENVIADO PARA AUTORIZAÇÃO',
            'A PAGAR - AUTORIZADO'
        ]
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

    data_selecionada = request.GET.get('data')
    forma_selecionada = request.GET.get('forma')

    lista_processos = processos_pendentes

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

    context = {
        'datas_agrupadas': datas_agrupadas,
        'formas_agrupadas': formas_agrupadas,
        'lista_processos': lista_processos,
        'data_selecionada': data_selecionada,
        'forma_selecionada': forma_selecionada,
        'pode_interagir': request.user.has_perm('processos.pode_operar_contas_pagar'),
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

                    status_aguardando, _ = StatusChoicesProcesso.objects.get_or_create(
                        status_choice__iexact='A PAGAR - PENDENTE AUTORIZAÇÃO',
                        defaults={'status_choice': 'A PAGAR - PENDENTE AUTORIZAÇÃO'}
                    )
                    processo.status = status_aguardando
                    processo.save()

                messages.success(request, f"Empenho registrado com sucesso! Processo #{processo.id} avançou para Autorização.")
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

            # Auto-create a ReembolsoCombustivel skeleton when transport is "VEÍCULO PRÓPRIO"
            meio = nova_diaria.meio_de_transporte
            if meio and 'VEÍCULO PRÓPRIO' in meio.meio_de_transporte.upper():
                status_pendente = StatusChoicesVerbasIndenizatorias.objects.filter(
                    status_choice__iexact='PEDIDO - CÁLCULO DE VALORES PENDENTE'
                ).first()
                ReembolsoCombustivel.objects.create(
                    diaria=nova_diaria,
                    beneficiario=nova_diaria.beneficiario,
                    numero_sequencial=nova_diaria.numero_sequencial,
                    data_saida=nova_diaria.data_saida,
                    data_retorno=nova_diaria.data_retorno,
                    cidade_origem=nova_diaria.cidade_origem,
                    cidade_destino=nova_diaria.cidade_destino,
                    objetivo=nova_diaria.objetivo,
                    distancia_km=0,
                    preco_combustivel=0,
                    valor_total=0,
                    status=status_pendente,
                )
                messages.info(
                    request,
                    'Reembolso de combustível criado automaticamente com status '
                    '"PEDIDO - CÁLCULO DE VALORES PENDENTE". '
                    'Verifique a distância e o preço médio do combustível para concluir o cálculo.'
                )

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

    credor_obj = itens.first().beneficiario

    status_padrao, _ = StatusChoicesProcesso.objects.get_or_create(
        status_choice__iexact='A PAGAR - PENDENTE AUTORIZAÇÃO',
        defaults={'status_choice': 'A PAGAR - PENDENTE AUTORIZAÇÃO'}
    )

    tipo_pagamento_verbas, _ = TiposDePagamento.objects.get_or_create(
        tipo_de_pagamento__iexact='Verba Indenizatória',
        defaults={'tipo_de_pagamento': 'Verba Indenizatória'}
    )

    novo_processo = Processo.objects.create(
        credor=credor_obj,
        valor_bruto=total,
        valor_liquido=total,
        detalhamento=f"Agrupamento de {tipo_verba.capitalize()}s",
        status=status_padrao,
        tipo_pagamento=tipo_pagamento_verbas,
    )

    for item in itens:
        item.processo = novo_processo
        item.save()

    messages.success(request, f"Processo #{novo_processo.id} gerado com sucesso!")
    return redirect('editar_processo_verbas', pk=novo_processo.id)


def editar_processo_verbas(request, pk):
    processo = get_object_or_404(Processo, id=pk)

    if request.method == 'POST':
        processo_form = ProcessoForm(request.POST, instance=processo, prefix='processo')
        pendencia_formset = PendenciaFormSet(request.POST, instance=processo, prefix='pendencia')

        if processo_form.is_valid() and pendencia_formset.is_valid():
            try:
                with transaction.atomic():
                    processo = processo_form.save()
                    pendencia_formset.save()

                messages.success(request, f'Processo #{processo.id} atualizado com sucesso!')
                return redirect('editar_processo_verbas', pk=processo.id)

            except Exception as e:
                print(f"🛑 Erro ao atualizar no banco: {e}")
                messages.error(request, 'Erro interno ao salvar as alterações.')
        else:
            messages.error(request, 'Verifique os erros no formulário.')

    else:
        processo_form = ProcessoForm(instance=processo, prefix='processo')
        pendencia_formset = PendenciaFormSet(instance=processo, prefix='pendencia')

    diarias = Diaria.objects.filter(processo=processo).prefetch_related('documentos__tipo')
    reembolsos = ReembolsoCombustivel.objects.filter(processo=processo).prefetch_related('documentos__tipo')
    jetons = Jeton.objects.filter(processo=processo).prefetch_related('documentos__tipo')
    auxilios = AuxilioRepresentacao.objects.filter(processo=processo).prefetch_related('documentos__tipo')
    tipos_doc = TiposDeDocumento.objects.filter(is_active=True)

    context = {
        'processo': processo,
        'processo_form': processo_form,
        'pendencia_formset': pendencia_formset,
        'diarias': diarias,
        'reembolsos': reembolsos,
        'jetons': jetons,
        'auxilios': auxilios,
        'tipos_documento': tipos_doc,
    }
    return render(request, 'editar_processo_verbas.html', context)


def api_add_documento_verba(request, tipo_verba, pk):
    """AJAX: Adiciona um documento a uma verba indenizatória específica."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método não permitido.'}, status=405)

    MAPA = {
        'diaria': (Diaria, DocumentoDiaria, 'diaria'),
        'reembolso': (ReembolsoCombustivel, DocumentoReembolso, 'reembolso'),
        'jeton': (Jeton, DocumentoJeton, 'jeton'),
        'auxilio': (AuxilioRepresentacao, DocumentoAuxilio, 'auxilio'),
    }

    if tipo_verba not in MAPA:
        return JsonResponse({'ok': False, 'error': 'Tipo de verba inválido.'}, status=400)

    ModeloVerba, ModeloDocumento, fk_name = MAPA[tipo_verba]
    verba = get_object_or_404(ModeloVerba, id=pk)

    arquivo = request.FILES.get('arquivo')
    tipo_id = request.POST.get('tipo')

    if not arquivo or not tipo_id:
        return JsonResponse({'ok': False, 'error': 'Arquivo e tipo de documento são obrigatórios.'}, status=400)

    EXTENSOES_PERMITIDAS = {'.pdf', '.jpg', '.jpeg', '.png'}
    _, ext = os.path.splitext(arquivo.name.lower())
    if ext not in EXTENSOES_PERMITIDAS:
        return JsonResponse({'ok': False, 'error': 'Formato não permitido. Use PDF, JPG ou PNG.'}, status=400)

    try:
        kwargs = {fk_name: verba, 'arquivo': arquivo, 'tipo_id': tipo_id}
        doc = ModeloDocumento.objects.create(**kwargs)
        return JsonResponse({'ok': True, 'doc_id': doc.id, 'arquivo_url': doc.arquivo.url, 'tipo': str(doc.tipo)})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


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

    status_padrao, _ = StatusChoicesProcesso.objects.get_or_create(
        status_choice__iexact='A PAGAR - PENDENTE AUTORIZAÇÃO',
        defaults={'status_choice': 'A PAGAR - PENDENTE AUTORIZAÇÃO'}
    )

    credor_orgao, _ = Credor.objects.get_or_create(
        nome="Órgão Arrecadador (A Definir)",
        defaults={'nome': "Órgão Arrecadador (A Definir)"}
    )

    tipo_pagamento_impostos, _ = TiposDePagamento.objects.get_or_create(
        tipo_de_pagamento="IMPOSTOS"
    )

    novo_processo = Processo.objects.create(
        credor=credor_orgao,
        valor_bruto=total_impostos,
        valor_liquido=total_impostos,
        detalhamento="Pagamento Agrupado de Impostos Retidos",
        observacao="Gerado automaticamente.",
        status=status_padrao,
        tipo_pagamento=tipo_pagamento_impostos
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
        queryset_base = DocumentoFiscal.objects.filter(retencoes__isnull=False).distinct()
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
    processos_lancados = Processo.objects.filter(
        status__status_choice__iexact='LANÇADO - AGUARDANDO COMPROVANTE'
    ).select_related('credor').order_by('credor__nome', 'id')

    processos_list = []
    for p in processos_lancados:
        processos_list.append({
            'id': p.id,
            'credor_nome': p.credor.nome if p.credor else 'Sem Credor',
            'valor_liquido': str(p.valor_liquido or '0.00'),
            'n_nota_empenho': p.n_nota_empenho or 'S/N',
        })

    context = {
        'processos_json': json.dumps(processos_list)
    }
    return render(request, 'painel_comprovantes.html', context)


def api_fatiar_comprovantes(request):
    if request.method == 'POST' and request.FILES.get('pdf_banco'):
        modo = request.POST.get('modo', 'auto')

        try:
            if modo == 'ia':
                resultados = processar_pdf_comprovantes_ia(request.FILES['pdf_banco'])
            elif modo == 'manual':
                resultados = fatiar_pdf_manual(request.FILES['pdf_banco'])
            else:  # modo == 'auto' (default): regex extraction, no AI cost
                resultados = processar_pdf_comprovantes(request.FILES['pdf_banco'])

            return JsonResponse({'sucesso': True, 'comprovantes': resultados, 'modo': modo})
        except Exception as e:
            return JsonResponse({'sucesso': False, 'erro': str(e)})
    return JsonResponse({'sucesso': False, 'erro': 'Arquivo não enviado.'})


@transaction.atomic
def api_vincular_comprovantes(request):
    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            processo_id = dados.get('processo_id')
            comprovantes = dados.get('comprovantes', [])

            if not processo_id:
                return JsonResponse({'sucesso': False, 'erro': 'ID do processo não informado.'})

            if not comprovantes:
                return JsonResponse({'sucesso': False, 'erro': 'Nenhum comprovante enviado.'})

            processo = get_object_or_404(Processo, id=processo_id)

            if not processo.status or processo.status.status_choice.upper() != 'LANÇADO - AGUARDANDO COMPROVANTE':
                return JsonResponse({
                    'sucesso': False,
                    'erro': f'Processo #{processo_id} não está no status correto. Status atual: {processo.status}'
                })

            # Validação: soma dos comprovantes deve ser igual ao valor líquido do processo
            soma_comprovantes = sum(
                float(c.get('valor_pago') or 0) for c in comprovantes
            )
            valor_liquido = float(processo.valor_liquido or 0)

            if abs(soma_comprovantes - valor_liquido) > 0.01:
                return JsonResponse({
                    'sucesso': False,
                    'erro': (
                        f'Soma dos comprovantes (R$ {soma_comprovantes:.2f}) é diferente do '
                        f'valor líquido do processo (R$ {valor_liquido:.2f}). '
                        f'Diferença: R$ {abs(soma_comprovantes - valor_liquido):.2f}'
                    )
                })

            status_pago, _ = StatusChoicesProcesso.objects.get_or_create(
                status_choice__iexact='PAGO - EM CONFERÊNCIA',
                defaults={'status_choice': 'PAGO - EM CONFERÊNCIA'}
            )

            tipo_comprovante, _ = TiposDeDocumento.objects.get_or_create(
                tipo_de_documento__iexact='Comprovante de Pagamento',
                defaults={'tipo_de_documento': 'Comprovante de Pagamento'}
            )

            data_pagamento_processo = None
            for idx, comp in enumerate(comprovantes):
                temp_path = comp.get('temp_path')
                if not temp_path:
                    continue

                valor_pago = comp.get('valor_pago')
                credor_nome = comp.get('credor_nome') or ''
                data_pagamento = comp.get('data_pagamento') or None

                # Use the first available payment date to update the process
                if data_pagamento and not data_pagamento_processo:
                    data_pagamento_processo = data_pagamento

                if default_storage.exists(temp_path):
                    with default_storage.open(temp_path) as temp_file:
                        conteudo_arquivo = temp_file.read()

                    nome_arquivo = f"Comprovante_Proc_{processo.id}_{idx + 1}.pdf"

                    DocumentoProcesso.objects.create(
                        processo=processo,
                        arquivo=ContentFile(conteudo_arquivo, name=nome_arquivo),
                        tipo=tipo_comprovante,
                        ordem=99
                    )

                    ComprovanteDePagamento.objects.create(
                        processo=processo,
                        credor_nome=credor_nome,
                        valor_pago=valor_pago,
                        data_pagamento=data_pagamento,
                        arquivo=ContentFile(conteudo_arquivo, name=nome_arquivo),
                    )

                    default_storage.delete(temp_path)

            processo.status = status_pago
            if data_pagamento_processo:
                processo.data_pagamento = data_pagamento_processo
            processo.save()

            return JsonResponse({
                'sucesso': True,
                'mensagem': f'Processo #{processo_id} baixado com sucesso! Status alterado para "PAGO - EM CONFERÊNCIA".'
            })

        except Exception as e:
            return JsonResponse({'sucesso': False, 'erro': str(e)})

    return JsonResponse({'sucesso': False, 'erro': 'Método inválido.'})


# ==========================================
# ETAPAS DE CONFERÊNCIA E TRAMITAÇÃO
# ==========================================

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
    return render(request, 'autorizacao.html', context)


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
    processos_pagos = Processo.objects.filter(status__status_choice__iexact='PAGO - EM CONFERÊNCIA')

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
        'processos': processos_aptos,
        'pode_interagir': request.user.has_perm('processos.pode_operar_contas_pagar'),
    }
    return render(request, 'conferencia.html', context)


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
    return render(request, 'conferencia_processo.html', context)


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def painel_contabilizacao_view(request):
    processos = Processo.objects.filter(status__status_choice__iexact='PAGO - A CONTABILIZAR').order_by('data_pagamento')
    context = {
        'processos': processos,
        'pendencia_form': PendenciaForm(),
        'pode_interagir': request.user.has_perm('processos.pode_contabilizar'),
    }

    return render(request, 'contabilizacao.html', context)


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
    return render(request, 'conselho.html', context)


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

    return render(request, 'arquivamento.html', {
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


def api_extrair_nota(request):
    if request.method == 'POST' and request.FILES.get('arquivo'):
        arquivo = request.FILES['arquivo']
        dados = extrair_dados_documento(arquivo, DocumentoFiscal)

        if dados:
            return JsonResponse({'status': 'success', 'dados': dados})

    return JsonResponse({'status': 'error', 'message': 'Falha na extração'}, status=400)


def api_extracao_universal(request):
    if request.method == 'POST' and request.FILES.get('arquivo'):
        arquivo = request.FILES['arquivo']
        tipo = request.POST.get('tipo')  # Pega o 'value' do <select> do frontend (empenho, notafiscal, boleto, siscac)

        try:
            # 1. Tratamento Local (SISCAC)
            # Como o SISCAC provavelmente usa o seu parser nativo (Regex/PyPDF), mantemos a função antiga
            if tipo == 'siscac':
                dados = extract_siscac_data(arquivo)

            # 2. Tratamento Inteligente (IA - Gemini)
            # Para os demais tipos, o nosso novo ai_utils.py assume o controlo e escolhe o Prompt certo
            else:
                dados = extrair_dados_documento(arquivo, tipo)

            # 3. Resposta ao Frontend
            if dados:
                return JsonResponse({'status': 'success', 'dados': dados})
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'A IA não conseguiu estruturar os dados deste documento. Tente novamente.'
                }, status=400)

        except Exception as e:
            # Imprime o erro no console do PythonAnywhere para facilitar o debug se a API do Gemini falhar
            import traceback
            traceback.print_exc()
            return JsonResponse({'status': 'error', 'message': f"Erro interno: {str(e)}"}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Requisição inválida ou arquivo ausente'}, status=400)


def api_processar_retencoes(request):
    """
    Recebe um arquivo PDF de Nota Fiscal, extrai os dados via IA e aplica as
    regras de negócio de retenções, retornando o JSON padronizado da Etapa 6.
    """
    if request.method != 'POST' or not request.FILES.get('arquivo'):
        return JsonResponse(
            {'status': 'error', 'message': 'Requisição inválida ou arquivo ausente'},
            status=400,
        )

    arquivo = request.FILES['arquivo']

    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        for chunk in arquivo.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        dados_extraidos = extract_data_with_llm(tmp_path)
        if dados_extraidos is None:
            return JsonResponse(
                {'status': 'error', 'message': 'A IA não conseguiu extrair os dados da nota fiscal.'},
                status=500,
            )

        resultado = process_invoice_taxes(dados_extraidos)
        return JsonResponse({'status': 'success', 'resultado': resultado})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Erro interno: {str(e)}'}, status=500)

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


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


def api_valor_unitario_diaria(request, beneficiario_id):
    try:
        credor = Credor.objects.select_related('cargo_funcao').get(id=beneficiario_id)

        if not credor.cargo_funcao_id:
            return JsonResponse({'sucesso': False, 'erro': 'Beneficiário sem cargo/função definido', 'valor_unitario': None})

        valor_unitario = Tabela_Valores_Unitarios_Verbas_Indenizatorias.get_valor_para_cargo_diaria(credor.cargo_funcao)

        if valor_unitario is not None:
            return JsonResponse({
                'sucesso': True,
                'valor_unitario': str(valor_unitario),
                'cargo_funcao': str(credor.cargo_funcao),
            })
        else:
            return JsonResponse({
                'sucesso': False,
                'erro': 'Nenhum valor unitário cadastrado para este cargo/função',
                'valor_unitario': None,
            })
    except Credor.DoesNotExist:
        return JsonResponse({'sucesso': False, 'erro': 'Beneficiário não encontrado', 'valor_unitario': None})


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


def gerenciar_diaria_view(request, pk):
    diaria = get_object_or_404(Diaria, id=pk)
    documentos = diaria.documentos.select_related('tipo').all()
    tipos_doc = TiposDeDocumento.objects.filter(is_active=True)

    if request.method == 'POST':
        arquivo = request.FILES.get('arquivo')
        tipo_id = request.POST.get('tipo')
        if arquivo and tipo_id:
            EXTENSOES_PERMITIDAS = {'.pdf', '.jpg', '.jpeg', '.png'}
            _, ext = os.path.splitext(arquivo.name.lower())
            if ext not in EXTENSOES_PERMITIDAS:
                messages.error(request, 'Formato de arquivo não permitido. Use PDF, JPG ou PNG.')
                return redirect('gerenciar_diaria', pk=diaria.id)
            try:
                DocumentoDiaria.objects.create(diaria=diaria, arquivo=arquivo, tipo_id=tipo_id)
                messages.success(request, 'Documento anexado com sucesso!')
            except Exception:
                messages.error(request, 'Erro ao salvar o documento. Tente novamente.')
        else:
            messages.error(request, 'Selecione um arquivo e um tipo de documento.')
        return redirect('gerenciar_diaria', pk=diaria.id)

    context = {
        'diaria': diaria,
        'documentos': documentos,
        'tipos_documento': tipos_doc,
    }
    return render(request, 'gerenciar_diaria.html', context)


def painel_suprimentos_view(request):
    suprimentos = SuprimentoDeFundos.objects.all().order_by('-id')
    return render(request, 'suprimentos_list.html', {'suprimentos': suprimentos})


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
    return render(request, 'gerenciar_suprimento.html', context)


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

    return render(request, 'add_suprimento.html', {'form': form})

def painel_pendencias_view(request):
    queryset_base = Pendencia.objects.select_related(
        'processo', 'status', 'tipo', 'processo__credor'
    ).all().order_by('-id')

    meu_filtro = PendenciaFilter(request.GET, queryset=queryset_base)

    context = {
        'meu_filtro': meu_filtro,
        'pendencias': meu_filtro.qs,
    }
    return render(request, 'painel_pendencias.html', context)

@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def painel_liquidacoes_view(request):
    # select_related otimiza a busca no banco, já puxando o processo e o emitente
    queryset_base = DocumentoFiscal.objects.select_related(
        'processo', 'nome_emitente', 'fiscal_contrato'
    ).all().order_by('-id')

    meu_filtro = DocumentoFiscalFilter(request.GET, queryset=queryset_base)

    context = {
        'meu_filtro': meu_filtro,
        'notas': meu_filtro.qs,
        'pode_interagir': request.user.has_perm('processos.pode_atestar_liquidacao'),
    }
    return render(request, 'painel_liquidacoes.html', context)

@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def alternar_ateste_nota(request, pk):
    """Permite atestar ou remover o ateste de uma nota diretamente pelo painel"""
    if request.method == 'POST':
        if not request.user.has_perm('processos.pode_atestar_liquidacao'):
            raise PermissionDenied
        nota = get_object_or_404(DocumentoFiscal, id=pk)

        # Inverte o status atual (Se True vira False, se False vira True)
        nota.atestada = not nota.atestada
        nota.save()

        if nota.atestada:
            messages.success(request, f'Nota Fiscal #{nota.numero_nota_fiscal} ATESTADA com sucesso!')
        else:
            messages.warning(request, f'Ateste da Nota Fiscal #{nota.numero_nota_fiscal} foi revogado.')

    return redirect('painel_liquidacoes')

def painel_autorizacao_diarias_view(request):
    queryset_base = Diaria.objects.select_related(
        'beneficiario', 'proponente', 'processo'
    ).all().order_by('-id')

    meu_filtro = DiariasAutorizacaoFilter(request.GET, queryset=queryset_base)

    context = {
        'meu_filtro': meu_filtro,
        'diarias': meu_filtro.qs,
    }
    return render(request, 'painel_autorizacao_diarias.html', context)

def alternar_autorizacao_diaria(request, pk):
    """Permite autorizar ou revogar a autorização de uma diária diretamente pelo painel"""
    if request.method == 'POST':
        diaria = get_object_or_404(Diaria, id=pk)

        diaria.autorizada = not diaria.autorizada
        diaria.save()

        if diaria.autorizada:
            messages.success(request, f'Diária #{diaria.numero_sequencial} AUTORIZADA com sucesso!')
        else:
            messages.warning(request, f'Autorização da Diária #{diaria.numero_sequencial} foi revogada.')

    return redirect('painel_autorizacao_diarias')

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
    return render(request, 'lancamento_bancario.html', context)


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
    return render(request, 'auditoria.html', context)


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
    return render(request, 'painel_contingencias.html', {
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

    return render(request, 'add_contingencia.html')


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
