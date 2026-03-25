import io
import os
import json
import random
import tempfile
import zipfile
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from faker import Faker
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db import transaction, IntegrityError
from django.db.models import Count, Q, F, Sum, Exists, OuterRef
from pypdf import PdfWriter
from ..forms import ProcessoForm, DocumentoFormSet, DocumentoFiscalFormSet, RetencaoFormSet, CredorForm, DiariaForm,ReembolsoForm, JetonForm, AuxilioForm, SuprimentoForm, PendenciaForm, PendenciaFormSet, DevolucaoForm
from ..validators import verificar_turnpike, STATUS_BLOQUEADOS_TOTAL, STATUS_SOMENTE_DOCUMENTOS
from ..utils import extract_siscac_data, mesclar_pdfs_em_memoria, processar_pdf_boleto, processar_pdf_comprovantes, gerar_termo_auditoria, fatiar_pdf_manual, parse_siscac_report, sync_siscac_payments
from ..utils_permissoes import group_required
from ..pdf_engine import gerar_documento_pdf
from ..ai_utils import extrair_dados_documento, extract_data_with_llm, extrair_codigos_barras_boletos, processar_pdf_comprovantes_ia
from ..invoice_processor import process_invoice_taxes
from ..models import Processo, DocumentoFiscal, StatusChoicesProcesso, Credor, Diaria, ReembolsoCombustivel, Jeton, AuxilioRepresentacao, TiposDeDocumento, DocumentoProcesso, DocumentoDiaria, DocumentoReembolso, DocumentoJeton, DocumentoAuxilio, CodigosImposto, RetencaoImposto, SuprimentoDeFundos, DespesaSuprimento, StatusChoicesPendencias, Pendencia, TiposDePendencias, ComprovanteDePagamento, Tabela_Valores_Unitarios_Verbas_Indenizatorias, DocumentoSuprimentoDeFundos, TiposDePagamento, Contingencia, StatusChoicesVerbasIndenizatorias, StatusChoicesRetencoes, MeiosDeTransporte, FormasDePagamento, ContasBancarias, CargosFuncoes, TagChoices, RegistroAcessoArquivo, Devolucao, ReuniaoConselho
from ..filters import ProcessoFilter, CredorFilter, DiariaFilter, ReembolsoFilter, JetonFilter, AuxilioFilter, RetencaoProcessoFilter, RetencaoNotaFilter, RetencaoIndividualFilter, PendenciaFilter, DocumentoFiscalFilter, ContingenciaFilter, DiariasAutorizacaoFilter, ArquivamentoFilter, DevolucaoFilter


def _is_cap_backoffice(user):
    """Returns True if the user is active and has CAP/backoffice privileges
    (superuser, staff, or the 'pode_operar_contas_pagar' permission)."""
    return user.is_active and (
        user.is_superuser
        or user.is_staff
        or user.has_perm('processos.pode_operar_contas_pagar')
    )


@login_required
@xframe_options_sameorigin
def download_arquivo_seguro(request, tipo_documento, documento_id):
    arquivo = None

    if tipo_documento == 'processo':
        doc = get_object_or_404(DocumentoProcesso, id=documento_id)
        arquivo = doc.arquivo
        if not _is_cap_backoffice(request.user):
            raise PermissionDenied

    elif tipo_documento == 'fiscal':
        doc = get_object_or_404(DocumentoFiscal, id=documento_id)
        if not doc.documento_vinculado:
            raise Http404
        arquivo = doc.documento_vinculado.arquivo
        if not _is_cap_backoffice(request.user):
            if doc.fiscal_contrato != request.user:
                raise PermissionDenied

    elif tipo_documento == 'comprovante':
        doc = get_object_or_404(ComprovanteDePagamento, id=documento_id)
        arquivo = doc.arquivo
        if not _is_cap_backoffice(request.user):
            raise PermissionDenied

    elif tipo_documento == 'suprimento':
        doc = get_object_or_404(DespesaSuprimento, id=documento_id)
        arquivo = doc.arquivo
        if not _is_cap_backoffice(request.user):
            user_in_supridos = request.user.groups.filter(name='SUPRIDOS').exists()
            suprimento = doc.suprimento
            is_encerrado = (
                suprimento.status is not None
                and suprimento.status.status_choice.upper() == 'ENCERRADO'
            )
            suprido_email = suprimento.suprido.email if suprimento.suprido else None
            email_match = bool(suprido_email and suprido_email == request.user.email)
            if not (user_in_supridos and not is_encerrado and email_match):
                raise PermissionDenied

    elif tipo_documento == 'devolucao':
        doc = get_object_or_404(Devolucao, id=documento_id)
        arquivo = doc.comprovante
        if not _is_cap_backoffice(request.user):
            raise PermissionDenied

    elif tipo_documento == 'verba_diaria_doc':
        doc = get_object_or_404(DocumentoDiaria, id=documento_id)
        arquivo = doc.arquivo
        if not _is_cap_backoffice(request.user):
            diaria = doc.diaria
            email_match = bool(
                diaria.beneficiario
                and diaria.beneficiario.email
                and diaria.beneficiario.email == request.user.email
            )
            proponente_match = diaria.proponente == request.user
            if not (email_match or proponente_match):
                raise PermissionDenied

    elif tipo_documento == 'verba_reembolso_doc':
        doc = get_object_or_404(DocumentoReembolso, id=documento_id)
        arquivo = doc.arquivo
        if not _is_cap_backoffice(request.user):
            reembolso = doc.reembolso
            email_match = bool(
                reembolso.beneficiario
                and reembolso.beneficiario.email
                and reembolso.beneficiario.email == request.user.email
            )
            if not email_match:
                raise PermissionDenied

    elif tipo_documento == 'verba_jeton_doc':
        doc = get_object_or_404(DocumentoJeton, id=documento_id)
        arquivo = doc.arquivo
        if not _is_cap_backoffice(request.user):
            jeton = doc.jeton
            email_match = bool(
                jeton.beneficiario
                and jeton.beneficiario.email
                and jeton.beneficiario.email == request.user.email
            )
            if not email_match:
                raise PermissionDenied

    elif tipo_documento == 'verba_auxilio_doc':
        doc = get_object_or_404(DocumentoAuxilio, id=documento_id)
        arquivo = doc.arquivo
        if not _is_cap_backoffice(request.user):
            auxilio = doc.auxilio
            email_match = bool(
                auxilio.beneficiario
                and auxilio.beneficiario.email
                and auxilio.beneficiario.email == request.user.email
            )
            if not email_match:
                raise PermissionDenied

    else:
        raise Http404

    if not arquivo or not arquivo.name:
        raise Http404

    try:
        file_handle = arquivo.open('rb')
    except (FileNotFoundError, OSError):
        raise Http404

    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')

    RegistroAcessoArquivo.objects.create(
        usuario=request.user,
        nome_arquivo=arquivo.name,
        ip_address=ip,
    )

    return FileResponse(file_handle, as_attachment=False)


def home_page(request):
    ORDER_FIELDS = {
        'id': 'id',
        'credor': 'credor__nome',
        'data_empenho': 'data_empenho',
        'status': 'status__status_choice',
        'tipo_pagamento': 'tipo_pagamento__tipo_de_pagamento',
        'valor_liquido': 'valor_liquido',
    }
    ordem = request.GET.get('ordem', 'id')
    direcao = request.GET.get('direcao', 'desc')

    order_field = ORDER_FIELDS.get(ordem, 'id')
    if direcao == 'desc':
        order_field = f'-{order_field}'

    processos_base = Processo.objects.all().order_by(order_field)
    meu_filtro = ProcessoFilter(request.GET, queryset=processos_base)
    processos_filtrados = meu_filtro.qs

    context = {
        'lista_processos': processos_filtrados,
        'meu_filtro': meu_filtro,
        'ordem': ordem,
        'direcao': direcao,
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

                    messages.success(request, f"Processo #{processo.id} inserido com sucesso!")
                    if request.POST.get('btn_goto_fiscais'):
                        return redirect('documentos_fiscais', pk=processo.id)
                    next_url = request.POST.get('next', '')
                    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                        return redirect(next_url)
                    return redirect('editar_processo', pk=processo.id)

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
        next_url = request.POST.get('next', '')

        if somente_documentos:
            # Only save document changes; process metadata is left untouched.
            if documento_formset.is_valid():
                try:
                    with transaction.atomic():
                        documento_formset.save()

                    messages.success(request, f'Documentos do Processo #{pk} atualizados com sucesso!')
                    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                        return redirect(next_url)
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

                    messages.success(request, f'Processo #{processo_saved.id} atualizado com sucesso!')
                    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                        return redirect(next_url)
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
        next_url = request.META.get('HTTP_REFERER', '')

    # Boleto indicators – only relevant when forma_pagamento is BOLETO/GERENCIADOR
    boleto_docs_qs = processo.documentos.select_related('tipo').filter(
        tipo__tipo_de_documento__icontains='boleto'
    )
    boleto_docs_count = boleto_docs_qs.count()
    boleto_barcodes_list = [
        doc.codigo_barras for doc in boleto_docs_qs if doc.codigo_barras
    ]
    boleto_barcodes_count = len(boleto_barcodes_list)

    context = {
        'processo_form': processo_form,
        'documento_formset': documento_formset,
        'pendencia_formset': pendencia_formset,
        'processo': processo,
        'status_inicial': status_inicial,
        'somente_documentos': somente_documentos,
        'aguardando_liquidacao': status_inicial.startswith('AGUARDANDO LIQUIDAÇÃO'),
        'documentos_fiscais_url': reverse('documentos_fiscais', kwargs={'pk': processo.id}),
        'boleto_docs_count': boleto_docs_count,
        'boleto_barcodes_list': boleto_barcodes_list,
        'boleto_barcodes_count': boleto_barcodes_count,
        'next_url': next_url,
    }

    return render(request, 'fluxo/editar_processo.html', context)


@login_required
def api_extrair_codigos_barras_processo(request, pk):
    """
    AJAX endpoint que dispara a extração de códigos de barras via IA para um processo,
    sem necessidade de salvar o formulário. Retorna JSON com o resultado.
    """
    if request.method != 'POST':
        return JsonResponse({'sucesso': False, 'erro': 'Método não permitido.'}, status=405)

    processo = get_object_or_404(Processo, id=pk)

    try:
        n_extraidos, n_falhas = _extrair_e_salvar_codigos_barras(processo)
    except Exception as e:
        return JsonResponse({'sucesso': False, 'erro': str(e)}, status=500)

    barcodes = [
        doc.codigo_barras
        for doc in processo.documentos.select_related('tipo').filter(
            tipo__tipo_de_documento__icontains='boleto'
        )
        if doc.codigo_barras
    ]

    return JsonResponse({
        'sucesso': True,
        'n_extraidos': n_extraidos,
        'n_falhas': n_falhas,
        'barcodes': barcodes,
    })


@login_required
def api_extrair_codigos_barras_upload(request):
    """
    AJAX endpoint that extracts barcodes from uploaded boleto PDF files.
    Accepts multiple files without requiring a saved Processo PK.
    Used by the add_process page before a processo is saved.
    """
    if request.method != 'POST':
        return JsonResponse({'sucesso': False, 'erro': 'Método não permitido.'}, status=405)

    files = request.FILES.getlist('boleto_files')
    if not files:
        return JsonResponse({'sucesso': False, 'erro': 'Nenhum arquivo enviado.'}, status=400)

    barcodes = []
    n_extraidos = 0
    n_falhas = 0

    for pdf_file in files:
        try:
            dados = processar_pdf_boleto(pdf_file)
            codigo = dados.get('codigo_barras', '') if dados else ''
            if codigo:
                barcodes.append(codigo)
                n_extraidos += 1
            else:
                barcodes.append(None)
                n_falhas += 1
        except Exception as e:
            print(f"⚠️ Erro ao extrair código de barras de '{getattr(pdf_file, 'name', 'arquivo')}': {e}", flush=True)
            barcodes.append(None)
            n_falhas += 1

    return JsonResponse({
        'sucesso': True,
        'n_extraidos': n_extraidos,
        'n_falhas': n_falhas,
        'barcodes': [b for b in barcodes if b],
    })


# ==========================================
# DOCUMENTOS FISCAIS: GERENCIAMENTO DE NOTAS FISCAIS
# ==========================================
@xframe_options_sameorigin
def visualizar_pdf_processo(request, processo_id):
    processo = get_object_or_404(Processo, id=processo_id)

    pdf_buffer = processo.gerar_pdf_consolidado()

    if pdf_buffer is None:
        return HttpResponse("Este processo ainda não possui documentos em PDF anexados.", status=404)

    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    nome_arquivo = f"Processo_{processo.n_nota_empenho or processo.id}.pdf"
    response['Content-Disposition'] = f'inline; filename="{nome_arquivo}"'
    return response


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

    contas_agrupadas = processos_pendentes.values(
        'conta__id',
        'conta__banco',
        'conta__agencia',
        'conta__conta',
        'conta__titular__nome',
    ).annotate(
        total=Count('id')
    ).order_by('conta__titular__nome', 'conta__banco', 'conta__agencia')

    data_selecionada = request.GET.get('data')
    forma_selecionada = request.GET.get('forma')
    status_selecionado = request.GET.get('status')
    conta_selecionada = request.GET.get('conta')
    ordem = request.GET.get('ordem', 'id')
    direcao = request.GET.get('direcao', 'asc')

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

    if conta_selecionada:
        if conta_selecionada == 'sem_conta':
            lista_processos = lista_processos.filter(conta__isnull=True)
        else:
            try:
                lista_processos = lista_processos.filter(conta__id=int(conta_selecionada))
            except (ValueError, TypeError):
                pass

    ORDER_FIELDS = {
        'id': 'id',
        'data_pagamento': 'data_pagamento',
        'credor': 'credor__nome',
        'valor_liquido': 'valor_liquido',
        'status': 'status__status_choice',
        'tipo_pagamento': 'tipo_pagamento__tipo_de_pagamento',
    }
    order_field = ORDER_FIELDS.get(ordem, 'id')
    if direcao == 'desc':
        order_field = f'-{order_field}'

    lista_processos = lista_processos.annotate(
        has_pendencias=Exists(Pendencia.objects.filter(processo=OuterRef('pk'))),
        has_retencoes=Exists(RetencaoImposto.objects.filter(nota_fiscal__processo=OuterRef('pk'))),
    ).order_by(order_field)

    context = {
        'datas_agrupadas': datas_agrupadas,
        'formas_agrupadas': formas_agrupadas,
        'statuses_agrupados': statuses_agrupados,
        'contas_agrupadas': contas_agrupadas,
        'lista_processos': lista_processos,
        'data_selecionada': data_selecionada,
        'forma_selecionada': forma_selecionada,
        'status_selecionado': status_selecionado,
        'conta_selecionada': conta_selecionada,
        'ordem': ordem,
        'direcao': direcao,
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
                    processo.save(update_fields=['n_nota_empenho', 'data_empenho'])
                    try:
                        processo.avancar_status('AGUARDANDO LIQUIDAÇÃO', usuario=request.user)
                    except ValidationError as ve:
                        raise ValueError(str(ve))

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

    try:
        with transaction.atomic():
            processo.avancar_status('A PAGAR - PENDENTE AUTORIZAÇÃO', usuario=request.user)

        messages.success(
            request,
            f'Processo #{pk} avançado com sucesso para "A Pagar - Pendente Autorização".'
        )
    except ValidationError as ve:
        for erro in ve.messages:
            messages.error(request, erro)
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
@group_required('ORDENADOR(A) DE DESPESA')
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
@group_required('ORDENADOR(A) DE DESPESA')
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
@group_required('ORDENADOR(A) DE DESPESA')
def recusar_autorizacao_view(request, pk):
    processo = get_object_or_404(Processo, id=pk)

    if request.method == 'POST':
        if not request.user.has_perm('processos.pode_autorizar_pagamento'):
            raise PermissionDenied
        form = PendenciaForm(request.POST)
        if form.is_valid():
            _registrar_recusa(request, processo, form, 'AGUARDANDO LIQUIDAÇÃO / ATESTE')
            messages.error(request, f'Processo #{processo.id} não autorizado e devolvido com pendência!')
        else:
            messages.warning(request, 'Erro ao registrar recusa. Verifique os dados da pendência.')

    return redirect('painel_autorizacao')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
@group_required('FUNCIONÁRIO(A) CONTAS A PAGAR')
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
@group_required('FUNCIONÁRIO(A) CONTAS A PAGAR')
def aprovar_conferencia_view(request, pk):
    messages.error(request, 'A aprovação direta foi desativada. Abra o processo para realizar a conferência.')
    return redirect('painel_conferencia')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
@group_required('FUNCIONÁRIO(A) CONTAS A PAGAR')
def iniciar_conferencia_view(request):
    """POST: store selected process IDs in session queue, redirect to first process."""
    if request.method == 'POST':
        return _iniciar_fila_sessao(
            request, 'processos.pode_operar_contas_pagar', 'conferencia_queue',
            'painel_conferencia', 'conferencia_processo'
        )
    return redirect('painel_conferencia')


def _build_history_record(record, modelo_label):
    """Build an enriched history record dict with changed fields and change reason."""
    HISTORY_TYPE_LABELS = {'+': 'Criação', '~': 'Alteração', '-': 'Exclusão'}
    changed_fields = []
    if record.history_type == '~':
        prev = record.prev_record
        if prev is not None:
            try:
                delta = record.diff_against(prev)
                for change in delta.changes:
                    changed_fields.append({
                        'field': change.field,
                        'old': change.old,
                        'new': change.new,
                    })
            except Exception:
                pass
    return {
        'modelo': modelo_label,
        'history_date': record.history_date,
        'history_user': record.history_user,
        'history_type': record.history_type,
        'history_type_label': HISTORY_TYPE_LABELS.get(record.history_type, record.history_type),
        'history_change_reason': getattr(record, 'history_change_reason', None),
        'str_repr': str(record),
        'changed_fields': changed_fields,
    }


def _iniciar_fila_sessao(request, permissao, queue_key, fallback_view, detail_view, extra_args=None):
    """Handles POST requests to start a review queue from a selected list of IDs."""
    if not request.user.has_perm(permissao):
        raise PermissionDenied

    ids_raw = request.POST.getlist('processo_ids')
    process_ids = [int(pid) for pid in ids_raw if pid.isdigit()]

    if not process_ids:
        messages.warning(request, 'Selecione ao menos um processo para iniciar a revisão.')
        return redirect(fallback_view, **(extra_args or {}))

    request.session[queue_key] = process_ids
    request.session.modified = True
    return redirect(detail_view, pk=process_ids[0])


def _handle_queue_navigation(request, pk, action, queue_key, fallback_view):
    """Handles 'sair', 'pular', and 'voltar' actions for the detailed review views."""
    queue = request.session.get(queue_key, [])
    current_index = queue.index(pk) if pk in queue else -1
    next_pk = queue[current_index + 1] if 0 <= current_index < len(queue) - 1 else None
    prev_pk = queue[current_index - 1] if current_index > 0 else None

    if action == 'sair':
        request.session.pop(queue_key, None)
        request.session.modified = True
        return redirect(fallback_view)

    if action == 'pular':
        if next_pk:
            return redirect(request.resolver_match.view_name, pk=next_pk)
        messages.info(request, 'Não há mais processos na fila. Retornando ao painel.')
        request.session.pop(queue_key, None)
        request.session.modified = True
        return redirect(fallback_view)

    if action == 'voltar':
        if prev_pk:
            return redirect(request.resolver_match.view_name, pk=prev_pk)
        messages.info(request, 'Não há processo anterior na fila.')
        return redirect(request.resolver_match.view_name, pk=pk)

    # Return context variables if no navigation action was taken
    return None, queue, current_index, next_pk, prev_pk


def _get_unified_history(pk):
    """Aggregates and sorts history records for a Processo and its related models."""
    processo = get_object_or_404(Processo, id=pk)
    history_records = []

    for record in processo.history.all().select_related('history_user'):
        history_records.append(_build_history_record(record, 'Processo'))
    for record in DocumentoProcesso.history.filter(processo_id=pk).select_related('history_user'):
        history_records.append(_build_history_record(record, 'Documento'))
    for record in Pendencia.history.filter(processo_id=pk).select_related('history_user'):
        history_records.append(_build_history_record(record, 'Pendência'))
    for record in DocumentoFiscal.history.filter(processo_id=pk).select_related('history_user'):
        history_records.append(_build_history_record(record, 'Nota Fiscal'))

    history_records.sort(key=lambda x: x['history_date'], reverse=True)
    return history_records


def _registrar_recusa(request, processo, form, status_devolucao):
    """Saves a pendency and rolls back the process status in an atomic transaction."""
    with transaction.atomic():
        pendencia = form.save(commit=False)
        pendencia.processo = processo
        status_pendencia, _ = StatusChoicesPendencias.objects.get_or_create(
            status_choice__iexact='A RESOLVER', defaults={'status_choice': 'A RESOLVER'}
        )
        pendencia.status = status_pendencia
        pendencia.save()
        processo.avancar_status(status_devolucao, usuario=request.user)


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
@group_required('FUNCIONÁRIO(A) CONTAS A PAGAR')
def conferencia_processo_view(request, pk):
    """Detailed conferência view for reviewing a single process."""
    processo = get_object_or_404(Processo, id=pk)

    if request.method == 'POST':
        action = request.POST.get('action', '')

        nav_result = _handle_queue_navigation(request, pk, action, 'conferencia_queue', 'painel_conferencia')
        if isinstance(nav_result, HttpResponse):
            return nav_result

        _, queue, current_index, next_pk, prev_pk = nav_result

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
                        processo.avancar_status('PAGO - A CONTABILIZAR', usuario=request.user)
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
    else:
        # GET: extract queue context (empty action triggers the tuple-return path)
        _, queue, current_index, next_pk, prev_pk = _handle_queue_navigation(
            request, pk, '', 'conferencia_queue', 'painel_conferencia'
        )

    # ── GET (or failed POST) ──────────────────────────────────────────────
    doc_formset = DocumentoFormSet(instance=processo, prefix='documentos')
    pendencia_formset = PendenciaFormSet(instance=processo, prefix='pendencias')
    pendencia_form = PendenciaForm()

    history_records = _get_unified_history(pk)

    contingencias = Contingencia.objects.filter(processo=processo).select_related(
        'solicitante', 'aprovado_por_supervisor', 'aprovado_por_ordenador', 'aprovado_por_conselho'
    ).order_by('-data_solicitacao')

    context = {
        'processo': processo,
        'doc_formset': doc_formset,
        'pendencia_formset': pendencia_formset,
        'pendencia_form': pendencia_form,
        'history_records': history_records,
        'contingencias': contingencias,
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
@group_required('CONTADOR(A)')
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
@group_required('CONTADOR(A)')
def iniciar_contabilizacao_view(request):
    """POST: store selected process IDs in session queue, redirect to first process."""
    if request.method == 'POST':
        return _iniciar_fila_sessao(
            request, 'processos.pode_contabilizar', 'contabilizacao_queue',
            'painel_contabilizacao', 'contabilizacao_processo'
        )
    return redirect('painel_contabilizacao')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
@group_required('CONTADOR(A)')
def contabilizacao_processo_view(request, pk):
    """Detailed contabilização view for reviewing a single process."""
    processo = get_object_or_404(Processo, id=pk)

    if request.method == 'POST':
        action = request.POST.get('action', '')

        nav_result = _handle_queue_navigation(request, pk, action, 'contabilizacao_queue', 'painel_contabilizacao')
        if isinstance(nav_result, HttpResponse):
            return nav_result

        _, queue, current_index, next_pk, prev_pk = nav_result

        if action in ('aprovar', 'rejeitar', 'salvar'):
            if not request.user.has_perm('processos.pode_contabilizar'):
                raise PermissionDenied

            if action == 'rejeitar':
                form = PendenciaForm(request.POST)
                if form.is_valid():
                    _registrar_recusa(request, processo, form, 'PAGO - EM CONFERÊNCIA')
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
                        processo.avancar_status('CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL', usuario=request.user)
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
    else:
        # GET: extract queue context (empty action triggers the tuple-return path)
        _, queue, current_index, next_pk, prev_pk = _handle_queue_navigation(
            request, pk, '', 'contabilizacao_queue', 'painel_contabilizacao'
        )

    # ── GET (or failed POST) ──────────────────────────────────────────────
    doc_formset = DocumentoFormSet(instance=processo, prefix='documentos')
    pendencia_formset = PendenciaFormSet(instance=processo, prefix='pendencias')
    pendencia_form = PendenciaForm()

    history_records = _get_unified_history(pk)

    contingencias = Contingencia.objects.filter(processo=processo).select_related(
        'solicitante', 'aprovado_por_supervisor', 'aprovado_por_ordenador', 'aprovado_por_conselho'
    ).order_by('-data_solicitacao')

    context = {
        'processo': processo,
        'doc_formset': doc_formset,
        'pendencia_formset': pendencia_formset,
        'pendencia_form': pendencia_form,
        'history_records': history_records,
        'contingencias': contingencias,
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
@group_required('CONTADOR(A)')
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
@group_required('CONTADOR(A)')
def recusar_contabilizacao_view(request, pk):
    processo = get_object_or_404(Processo, id=pk)

    if request.method == 'POST':
        if not request.user.has_perm('processos.pode_contabilizar'):
            raise PermissionDenied
        form = PendenciaForm(request.POST)
        if form.is_valid():
            _registrar_recusa(request, processo, form, 'PAGO - EM CONFERÊNCIA')
            messages.error(request, f'Processo #{processo.id} recusado pela Contabilidade e devolvido para a Conferência!')
        else:
            messages.warning(request, 'Erro ao registrar recusa. Verifique os dados da pendência.')

    return redirect('painel_contabilizacao')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
@group_required('CONSELHEIRO(A) FISCAL')
def painel_conselho_view(request):
    reunioes_ativas = ReuniaoConselho.objects.filter(status__in=['AGENDADA', 'EM_ANALISE']).order_by('-numero')
    processos_sem_reuniao = Processo.objects.filter(
        status__status_choice__iexact='CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL',
        reuniao_conselho__isnull=True,
    ).order_by('data_pagamento')
    context = {
        'reunioes_ativas': reunioes_ativas,
        'processos_sem_reuniao': processos_sem_reuniao,
        'pode_interagir': request.user.has_perm('processos.pode_auditar_conselho'),
    }
    return render(request, 'fluxo/conselho.html', context)


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
@group_required('CONSELHEIRO(A) FISCAL')
def iniciar_conselho_view(request):
    """POST: store selected process IDs in session queue, redirect to first process."""
    if request.method == 'POST':
        return _iniciar_fila_sessao(
            request, 'processos.pode_auditar_conselho', 'conselho_queue',
            'painel_conselho', 'conselho_processo'
        )
    return redirect('painel_conselho')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
@group_required('CONSELHEIRO(A) FISCAL')
def conselho_processo_view(request, pk):
    """Completely readonly view for Conselho Fiscal — can only approve or reject."""
    processo = get_object_or_404(Processo, id=pk)

    if request.method == 'POST':
        action = request.POST.get('action', '')

        nav_result = _handle_queue_navigation(request, pk, action, 'conselho_queue', 'painel_conselho')
        if isinstance(nav_result, HttpResponse):
            return nav_result

        _, queue, current_index, next_pk, prev_pk = nav_result

        if action in ('aprovar', 'rejeitar'):
            if not request.user.has_perm('processos.pode_auditar_conselho'):
                raise PermissionDenied

            if action == 'aprovar':
                processo.avancar_status('APROVADO - PENDENTE ARQUIVAMENTO', usuario=request.user)
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
                    _registrar_recusa(request, processo, form, 'PAGO - A CONTABILIZAR')
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
    else:
        # GET: extract queue context (empty action triggers the tuple-return path)
        _, queue, current_index, next_pk, prev_pk = _handle_queue_navigation(
            request, pk, '', 'conselho_queue', 'painel_conselho'
        )

    # ── GET (or failed POST) ──────────────────────────────────────────────
    pendencia_form = PendenciaForm()

    history_records = _get_unified_history(pk)

    contingencias = Contingencia.objects.filter(processo=processo).select_related(
        'solicitante', 'aprovado_por_supervisor', 'aprovado_por_ordenador', 'aprovado_por_conselho'
    ).order_by('-data_solicitacao')

    context = {
        'processo': processo,
        'pendencia_form': pendencia_form,
        'history_records': history_records,
        'contingencias': contingencias,
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
@group_required('CONSELHEIRO(A) FISCAL')
def aprovar_conselho_view(request, pk):
    if request.method == 'POST':
        if not request.user.has_perm('processos.pode_auditar_conselho'):
            raise PermissionDenied
        processo = get_object_or_404(Processo, id=pk)
        status_arquivamento, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact='APROVADO - PENDENTE ARQUIVAMENTO',
            defaults={'status_choice': 'APROVADO - PENDENTE ARQUIVAMENTO'}
        )
        processo.status = status_arquivamento
        processo.save()
        messages.success(request, f'Processo #{processo.id} aprovado pelo Conselho e liberado para arquivamento!')
    return redirect('painel_conselho')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
@group_required('CONSELHEIRO(A) FISCAL')
def recusar_conselho_view(request, pk):
    processo = get_object_or_404(Processo, id=pk)

    if request.method == 'POST':
        if not request.user.has_perm('processos.pode_auditar_conselho'):
            raise PermissionDenied
        form = PendenciaForm(request.POST)
        if form.is_valid():
            _registrar_recusa(request, processo, form, 'PAGO - A CONTABILIZAR')
            messages.error(request, f'Processo #{processo.id} recusado pelo Conselho Fiscal e devolvido para a Contabilidade!')
        else:
            messages.warning(request, 'Erro ao registrar recusa. Verifique os dados da pendência.')

    return redirect('painel_conselho')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def gerenciar_reunioes_view(request):
    """Lista todas as ReuniaoConselho e permite criar uma nova."""
    if request.method == 'POST':
        if not request.user.has_perm('processos.pode_auditar_conselho'):
            raise PermissionDenied
        numero = request.POST.get('numero', '').strip()
        trimestre_referencia = request.POST.get('trimestre_referencia', '').strip()
        data_reuniao = request.POST.get('data_reuniao') or None
        if numero and trimestre_referencia:
            try:
                ReuniaoConselho.objects.create(
                    numero=int(numero),
                    trimestre_referencia=trimestre_referencia,
                    data_reuniao=data_reuniao,
                )
                messages.success(request, f'{numero}ª Reunião criada com sucesso.')
            except ValueError:
                messages.error(request, 'Número da reunião inválido.')
            except IntegrityError as e:
                messages.error(request, f'Erro de integridade ao criar reunião: {e}')
        else:
            messages.warning(request, 'Preencha o número e o trimestre de referência.')
        return redirect('gerenciar_reunioes')

    reunioes = ReuniaoConselho.objects.all()
    context = {
        'reunioes': reunioes,
        'pode_interagir': request.user.has_perm('processos.pode_auditar_conselho'),
    }
    return render(request, 'processos/gerenciar_reunioes.html', context)


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def montar_pauta_reuniao_view(request, reuniao_id):
    """Permite adicionar processos elegíveis a uma reunião específica."""
    reuniao = get_object_or_404(ReuniaoConselho, id=reuniao_id)

    if request.method == 'POST':
        if not request.user.has_perm('processos.pode_auditar_conselho'):
            raise PermissionDenied
        processos_ids = request.POST.getlist('processos_selecionados')
        if processos_ids:
            updated = Processo.objects.filter(id__in=processos_ids).update(reuniao_conselho=reuniao)
            messages.success(request, f'{updated} processo(s) adicionado(s) à pauta.')
        else:
            messages.warning(request, 'Nenhum processo selecionado.')
        return redirect('montar_pauta_reuniao', reuniao_id=reuniao_id)

    processos_na_pauta = reuniao.processos_em_pauta.all().order_by('data_pagamento')
    processos_elegiveis = Processo.objects.filter(
        status__status_choice__iexact='CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL',
        reuniao_conselho__isnull=True,
    ).order_by('data_pagamento')

    context = {
        'reuniao': reuniao,
        'processos_na_pauta': processos_na_pauta,
        'processos_elegiveis': processos_elegiveis,
        'pode_interagir': request.user.has_perm('processos.pode_auditar_conselho'),
    }
    return render(request, 'processos/montar_pauta_conselho.html', context)


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def analise_reuniao_view(request, reuniao_id):
    """Painel de análise para Conselheiros: lista processos de uma reunião específica."""
    if not request.user.has_perm('processos.pode_auditar_conselho'):
        raise PermissionDenied
    reuniao = get_object_or_404(ReuniaoConselho, id=reuniao_id)
    processos_na_pauta = reuniao.processos_em_pauta.all().order_by('data_pagamento')
    context = {
        'reuniao': reuniao,
        'processos': processos_na_pauta,
        'pendencia_form': PendenciaForm(),
        'pode_interagir': True,
    }
    return render(request, 'processos/analise_reuniao.html', context)


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def iniciar_conselho_reuniao_view(request, reuniao_id):
    """POST: store process IDs for a specific meeting in session queue."""
    if request.method == 'POST':
        get_object_or_404(ReuniaoConselho, id=reuniao_id)
        return _iniciar_fila_sessao(
            request, 'processos.pode_auditar_conselho', 'conselho_queue',
            'analise_reuniao', 'conselho_processo',
            extra_args={'reuniao_id': reuniao_id}
        )
    return redirect('painel_conselho')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
@group_required('FUNCIONÁRIO(A) CONTAS A PAGAR')
def painel_arquivamento_view(request):
    processos_pendentes = Processo.objects.filter(
        status__status_choice__iexact='APROVADO - PENDENTE ARQUIVAMENTO'
    ).order_by('data_pagamento')

    arquivados_qs = Processo.objects.filter(
        status__status_choice__iexact='ARQUIVADO'
    ).order_by('-id')

    arquivamento_filtro = ArquivamentoFilter(request.GET or None, queryset=arquivados_qs)
    processos_arquivados = arquivamento_filtro.qs

    return render(request, 'fluxo/arquivamento.html', {
        'processos_pendentes': processos_pendentes,
        'processos_arquivados': processos_arquivados,
        'processos_arquivados_count': processos_arquivados.count(),
        'arquivamento_filtro': arquivamento_filtro,
        'pode_interagir': request.user.has_perm('processos.pode_arquivar'),
    })


@login_required
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
@group_required('FUNCIONÁRIO(A) CONTAS A PAGAR')
def arquivar_processo_view(request, pk):
    if request.method != 'POST':
        return redirect('painel_arquivamento')

    if not request.user.has_perm('processos.pode_arquivar'):
        raise PermissionDenied

    processo = get_object_or_404(Processo, id=pk)

    status_atual = processo.status.status_choice if processo.status else ''
    if status_atual.upper() != 'APROVADO - PENDENTE ARQUIVAMENTO':
        messages.error(request, f'Processo #{processo.id} não está no status correto para arquivamento.')
        return redirect('painel_arquivamento')

    pdf_buffer = processo.gerar_pdf_consolidado()

    if pdf_buffer is None:
        messages.error(request, f'Processo #{processo.id} não possui documentos para arquivar.')
        return redirect('painel_arquivamento')

    pdf_bytes = pdf_buffer.read()

    nome_arquivo = f'processo_{processo.id}_consolidado.pdf'
    with transaction.atomic():
        processo.arquivo_final.save(nome_arquivo, ContentFile(pdf_bytes), save=False)
        processo.save(update_fields=['arquivo_final'])
        processo.avancar_status('ARQUIVADO', usuario=request.user)

    messages.success(request, f'Processo #{processo.id} arquivado definitivamente com sucesso!')
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
                try:
                    valor_num = float(p.valor_liquido) if p.valor_liquido else 0.0
                    valor_formatado = f"{valor_num:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                except (ValueError, TypeError):
                    valor_formatado = "0,00"

                pagamento = p.detalhes_pagamento

                resultados.append({
                    'id': p.id,
                    'empenho': p.n_nota_empenho or "S/N",
                    'credor': p.credor.nome if p.credor else "Sem Credor",
                    'valor': valor_formatado,
                    'forma': p.forma_pagamento.forma_de_pagamento if p.forma_pagamento else "N/A",
                    'detalhe_tipo': pagamento['tipo_formatado'],
                    'detalhe_valor': pagamento['valor_formatado'],
                    'codigos_barras': pagamento['codigos_barras'],
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
        tipo = p.tipo_pagamento.tipo_de_pagamento.upper() if p.tipo_pagamento else ''

        if tipo == 'GERENCIADOR/BOLETO BANCÁRIO' or 'boleto' in forma or 'gerenciador' in forma:
            codigos_barras = [
                doc.codigo_barras
                for doc in p.documentos.all()
                if doc.codigo_barras
            ]
            dados_pagamento = {
                'tipo': 'codigo_barras',
                'codigos_barras': codigos_barras,
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
    ).select_related('forma_pagamento', 'tipo_pagamento', 'conta', 'credor__conta', 'status').prefetch_related('documentos').order_by('forma_pagamento__forma_de_pagamento', 'id')

    a_pagar_qs = processos_qs.filter(status=status_autorizado) if status_autorizado else processos_qs.none()
    lancados_qs = processos_qs.filter(status=status_lancado) if status_lancado else processos_qs.none()

    processos_a_pagar, totais_a_pagar = _build_detalhes_pagamento(a_pagar_qs)
    processos_lancados, totais_lancados = _build_detalhes_pagamento(lancados_qs)

    totais = {}
    for forma, val in totais_a_pagar.items():
        totais[forma] = totais.get(forma, 0) + val
    for forma, val in totais_lancados.items():
        totais[forma] = totais.get(forma, 0) + val

    total_a_pagar = sum(totais_a_pagar.values())
    total_lancados = sum(totais_lancados.values())
    total_geral = total_a_pagar + total_lancados

    context = {
        'processos_a_pagar': processos_a_pagar,
        'processos_lancados': processos_lancados,
        'totais': totais,
        'totais_a_pagar': totais_a_pagar,
        'totais_lancados': totais_lancados,
        'total_a_pagar': total_a_pagar,
        'total_lancados': total_lancados,
        'total_geral': total_geral,
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
@xframe_options_sameorigin
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
                'url': reverse('download_arquivo_seguro', args=['processo', doc.id]),
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
@user_passes_test(lambda u: u.has_perm('processos.acesso_backoffice'))
def analisar_contingencia_view(request, pk):
    """POST: Approve or reject a pending Contingencia by its PK."""
    _CAMPOS_PERMITIDOS_CONTINGENCIA = {
        'n_nota_empenho', 'data_empenho', 'valor_bruto', 'valor_liquido',
        'ano_exercicio', 'n_pagamento_siscac', 'data_vencimento', 'data_pagamento',
        'observacao', 'detalhamento', 'credor_id', 'forma_pagamento_id',
        'tipo_pagamento_id', 'conta_id', 'tag_id',
    }

    contingencia = get_object_or_404(Contingencia, pk=pk)
    processo = contingencia.processo

    if request.method == 'POST':
        action = request.POST.get('action', '').strip()

        if action == 'aprovar':
            if 'novo_valor_liquido' in contingencia.dados_propostos:
                raw_value = contingencia.dados_propostos['novo_valor_liquido']
                if isinstance(raw_value, str):
                    raw_value = raw_value.replace('.', '').replace(',', '.')
                try:
                    novo_valor_liquido = Decimal(str(raw_value))
                except (InvalidOperation, ValueError):
                    messages.error(request, 'O valor líquido proposto na contingência é inválido.')
                    return redirect('painel_contingencias')

                soma_comprovantes = sum(
                    comp.valor_pago for comp in processo.comprovantes_pagamento.all()
                    if comp.valor_pago is not None
                )

                if abs(novo_valor_liquido - Decimal(str(soma_comprovantes))) > Decimal('0.01'):
                    messages.error(
                        request,
                        'A contingência não pode ser aprovada. O novo valor líquido proposto não corresponde à '
                        'soma dos comprovantes bancários anexados no sistema. O setor responsável deve anexar '
                        'os comprovantes restantes antes da aprovação.'
                    )
                    return redirect('painel_contingencias')

            campos_alterados = []
            for campo, valor in contingencia.dados_propostos.items():
                if campo in _CAMPOS_PERMITIDOS_CONTINGENCIA and hasattr(processo, campo):
                    setattr(processo, campo, valor)
                    campos_alterados.append(campo)

            processo.em_contingencia = False
            campos_alterados.append('em_contingencia')
            processo.save(update_fields=campos_alterados)

            contingencia.status = 'APROVADA'
            contingencia.save(update_fields=['status'])

            messages.success(
                request,
                f'Contingência #{contingencia.pk} aprovada com sucesso. O Processo #{processo.pk} foi atualizado.'
            )

        elif action == 'rejeitar':
            contingencia.status = 'REJEITADA'
            contingencia.save(update_fields=['status'])

            processo.em_contingencia = False
            processo.save(update_fields=['em_contingencia'])

            messages.warning(
                request,
                f'Contingência #{contingencia.pk} rejeitada.'
            )

        else:
            messages.error(request, 'Ação inválida.')

    return redirect('painel_contingencias')


@login_required
@user_passes_test(lambda u: u.has_perm('processos.pode_autorizar_pagamento'))
@xframe_options_sameorigin
def gerar_autorizacao_pagamento_view(request, pk):
    """
    Gera e serve o PDF "Termo de Autorização de Pagamento" para o processo indicado.
    """
    processo = get_object_or_404(Processo, pk=pk)
    pdf_bytes = gerar_documento_pdf('autorizacao', processo)
    nome_arquivo = f"Autorizacao_Pagamento_Proc_{processo.id}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nome_arquivo}"'
    return response


@login_required
@user_passes_test(lambda u: u.has_perm('processos.pode_auditar_conselho'))
@xframe_options_sameorigin
def gerar_parecer_conselho_view(request, pk):
    """
    Gera e serve o PDF "Parecer do Conselho Fiscal" para o processo indicado.
    """
    processo = get_object_or_404(Processo, pk=pk)
    numero_reuniao = processo.reuniao_conselho.numero if processo.reuniao_conselho else None
    pdf_bytes = gerar_documento_pdf('conselho_fiscal', processo, numero_reuniao=numero_reuniao)
    nome_arquivo = f"Parecer_Conselho_Fiscal_Proc_{processo.id}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nome_arquivo}"'
    return response


_fake_generator = Faker('pt_BR')
_MIN_FAKE_ANO_EXERCICIO = 2020


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

    for cargo in ["Analista", "Assessor", "Diretor", "Técnico Administrativo"]:
        CargosFuncoes.objects.get_or_create(grupo="FUNCIONÁRIOS", cargo_funcao=cargo)
    for cargo in ["Empresa de TI", "Empresa de Limpeza"]:
        CargosFuncoes.objects.get_or_create(grupo="FORNECEDORES", cargo_funcao=cargo)

    if not ContasBancarias.objects.exists():
        ContasBancarias.objects.create(
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
        ContasBancarias.objects.get_or_create(
            banco="Caixa Econômica Federal",
            agencia="1234",
            defaults={
                "conta": str(random.randint(10000, 99999)),
            },
        )
        conta = ContasBancarias.objects.first()
        Credor.objects.create(
            nome=_fake_generator.company(),
            cpf_cnpj=_fake_generator.cnpj(),
            tipo='PJ',
            conta=conta,
            email=_fake_generator.email(),
            telefone=_fake_generator.phone_number()[:20],
            chave_pix=_fake_generator.email(),
        )

    if not Credor.objects.filter(tipo='PF').exists():
        conta = ContasBancarias.objects.first()
        cargo = CargosFuncoes.objects.filter(grupo="FUNCIONÁRIOS").first()
        Credor.objects.create(
            nome=_fake_generator.name(),
            cpf_cnpj=_fake_generator.cpf(),
            tipo='PF',
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
    from django.contrib.auth.models import User
    credores_pj = list(Credor.objects.filter(tipo='PJ'))
    fiscais = list(User.objects.filter(groups__name='FISCAL DE CONTRATO'))
    if not fiscais:
        fiscais = list(User.objects.all())
    if not credores_pj:
        credores_pj = list(Credor.objects.all())

    created = 0
    for i in range(n):
        processo = random.choice(processos)
        emitente = random.choice(credores_pj) if credores_pj else None
        fiscal = random.choice(fiscais) if fiscais else None
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
        data_saida = _fake_generator.date_between(start_date="-6m", end_date="today")
        dias = random.randint(1, 10)
        data_retorno = data_saida + timedelta(days=dias)
        quantidade = Decimal(str(round(random.uniform(0.5, float(dias)), 1)))
        existing_count = Diaria.objects.count()
        numero_seq = f"DIA{date.today().year}{str(existing_count + i + 1).zfill(5)}"
        processo = random.choice(processos) if processos else None
        Diaria.objects.create(
            processo=processo,
            numero_siscac=numero_seq,
            beneficiario=beneficiario,
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


@login_required
def sincronizar_siscac(request):
    context = {}
    if request.method == 'POST':
        if request.POST.get('action') == 'forcar_sync':
            from ..models import Processo
            force_sync_ids = request.POST.getlist('force_sync_ids')
            count = 0
            errors = 0
            for item in force_sync_ids:
                try:
                    processo_id, siscac_pg = item.split('|', 1)
                    processo = Processo.objects.get(id=int(processo_id))
                    processo.n_pagamento_siscac = siscac_pg
                    processo.save(update_fields=['n_pagamento_siscac'])
                    count += 1
                except Exception:
                    errors += 1
            if count:
                messages.success(request, f'{count} processo(s) sincronizado(s) com sucesso.')
            if errors:
                messages.error(request, f'{errors} item(ns) não puderam ser sincronizados.')
            return redirect('sincronizar_siscac')
        elif 'siscac_pdf' in request.FILES:
            pdf_file = request.FILES['siscac_pdf']
            if not pdf_file.name.lower().endswith('.pdf'):
                messages.error(request, 'O arquivo enviado não é um PDF válido.')
                return render(request, 'fluxo/sincronizar_siscac.html', context)
            try:
                extracted = parse_siscac_report(pdf_file)
                results = sync_siscac_payments(extracted)
                context['resultados'] = results
            except Exception as e:
                messages.error(request, f'Erro ao processar o relatório SISCAC: {e}')
    return render(request, 'fluxo/sincronizar_siscac.html', context)


@login_required
def registrar_devolucao_view(request, processo_id):
    processo = get_object_or_404(Processo, id=processo_id)

    if request.method == 'POST':
        form = DevolucaoForm(request.POST, request.FILES)
        if form.is_valid():
            devolucao = form.save(commit=False)
            devolucao.processo = processo
            devolucao.save()
            messages.success(request, 'Devolução registrada com sucesso.')
            return redirect('process_detail', processo.id)
    else:
        form = DevolucaoForm()

    return render(request, 'fluxo/add_devolucao.html', {
        'form': form,
        'processo': processo,
    })


@login_required
def process_detail_view(request, pk):
    processo = get_object_or_404(Processo, pk=pk)
    documentos = processo.documentos.all()
    status_permite_devolucao = {
        'PAGO - A CONTABILIZAR',
        'CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL',
        'APROVADO - PENDENTE ARQUIVAMENTO',
        'ARQUIVADO',
    }
    pode_registrar_devolucao = (
        processo.status and processo.status.status_choice in status_permite_devolucao
    )
    return render(request, 'fluxo/process_detail.html', {
        'processo': processo,
        'documentos': documentos,
        'pode_registrar_devolucao': pode_registrar_devolucao,
    })


@login_required
def painel_devolucoes_view(request):
    queryset = Devolucao.objects.select_related('processo', 'processo__credor').order_by('-data_devolucao')
    meu_filtro = DevolucaoFilter(request.GET, queryset=queryset)
    total_valor = meu_filtro.qs.aggregate(total=Sum('valor_devolvido'))['total'] or Decimal('0')
    return render(request, 'fluxo/devolucoes_list.html', {
        'filter': meu_filtro,
        'devolucoes': meu_filtro.qs,
        'total_valor': total_valor,
    })
