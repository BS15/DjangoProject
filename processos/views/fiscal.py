import os
import json
import tempfile
from datetime import date, datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Sum, Exists, OuterRef
from ..validators import verificar_turnpike
from ..utils import processar_pdf_comprovantes, fatiar_pdf_manual, processar_pdf_comprovantes_ia
from ..ai_utils import extrair_dados_documento, extract_data_with_llm
from ..invoice_processor import process_invoice_taxes
from ..models import (
    Processo, DocumentoFiscal, Credor, TiposDeDocumento, DocumentoProcesso,
    CodigosImposto, RetencaoImposto, StatusChoicesProcesso, TiposDePagamento,
    StatusChoicesPendencias, Pendencia, TiposDePendencias, ComprovanteDePagamento,
)
from ..filters import RetencaoProcessoFilter, RetencaoNotaFilter, RetencaoIndividualFilter, DocumentoFiscalFilter


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
    return render(request, 'fiscal/documentos_fiscais.html', context)


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

    return render(request, 'fiscal/painel_impostos.html', context)


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

    import json as _json
    context = {
        'processos_json': _json.dumps(processos_list)
    }
    return render(request, 'fiscal/painel_comprovantes.html', context)


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
            # (esta verificação é realizada dentro de verificar_turnpike via avancar_status)

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

            # Advance status via avancar_status (includes turnpike validation)
            try:
                processo.avancar_status('PAGO - EM CONFERÊNCIA')
            except ValidationError as ve:
                return JsonResponse({'sucesso': False, 'erro': ' '.join(ve.messages)})

            if data_pagamento_processo:
                processo.data_pagamento = data_pagamento_processo
                processo.save(update_fields=['data_pagamento'])

            return JsonResponse({
                'sucesso': True,
                'mensagem': f'Processo #{processo_id} baixado com sucesso! Status alterado para "PAGO - EM CONFERÊNCIA".'
            })

        except Exception as e:
            return JsonResponse({'sucesso': False, 'erro': str(e)})

    return JsonResponse({'sucesso': False, 'erro': 'Método inválido.'})


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
    return render(request, 'fiscal/painel_liquidacoes.html', context)


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
                from ..utils import extract_siscac_data
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


@login_required
def painel_reinf_view(request):
    """
    Painel EFD-Reinf — exibe as retenções separadas em:
      • Série 2000  (INSS / R-2010)
      • Série 4000  (IRRF / CSRF / R-4010 / R-4020)

    Aceita os parâmetros GET `mes` (1-12) e `ano` (YYYY) para filtrar
    pela competência.  Quando omitidos, usa o mês/ano corrente.
    O parâmetro `todos=1` ignora o filtro de competência e retorna
    todos os lançamentos de todas as competências.
    """
    from ..reinf_services import get_serie_2000_data, get_serie_4000_data

    today = date.today()

    # ?todos=1  →  show every entry regardless of competência
    todos = request.GET.get('todos') == '1'

    if todos:
        mes = None
        ano = None
    else:
        try:
            mes = int(request.GET.get('mes', today.month))
            ano = int(request.GET.get('ano', today.year))
            if not (1 <= mes <= 12):
                raise ValueError
        except (ValueError, TypeError):
            mes = today.month
            ano = today.year

    serie_2000 = get_serie_2000_data(mes, ano)
    serie_4000 = get_serie_4000_data(mes, ano)

    context = {
        'mes': mes if mes is not None else today.month,
        'ano': ano if ano is not None else today.year,
        'todos': todos,
        'serie_2000': serie_2000,
        'serie_4000': serie_4000,
        'meses': range(1, 13),
        'anos': range(today.year - 4, today.year + 2),
    }
    return render(request, 'fiscal/painel_reinf.html', context)


@login_required
def gerar_lote_reinf_view(request):
    """
    Generate EFD-Reinf XML batch files (lotes) for R-2010 (INSS) and
    R-4020 (Federais) based on the given competência (mes/ano) and return
    them packaged as a downloadable .zip file.

    GET parameters:
    - mes: month 1–12 (defaults to current month)
    - ano: year YYYY  (defaults to current year)

    Returns 404 if no attested retentions exist for the requested period.
    """
    import io
    import zipfile
    from ..reinf_services import gerar_lotes_reinf

    today = date.today()
    try:
        mes = int(request.GET.get('mes', today.month))
        ano = int(request.GET.get('ano', today.year))
        if not (1 <= mes <= 12):
            raise ValueError
    except (ValueError, TypeError):
        mes = today.month
        ano = today.year

    try:
        xmls = gerar_lotes_reinf(mes, ano)
    except ValueError as exc:
        return HttpResponse(str(exc), status=404)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename, xml_content in xmls.items():
            zf.writestr(filename, xml_content)

    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/zip')
    zip_filename = f'lotes_reinf_{ano}{mes:02d}.zip'
    response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
    return response
