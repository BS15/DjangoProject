import os
from datetime import date, timedelta
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from ..forms import DiariaForm, ReembolsoForm, JetonForm, AuxilioForm, ProcessoForm, PendenciaFormSet
from ..models import (
    Diaria, ReembolsoCombustivel, Jeton, AuxilioRepresentacao, TiposDeDocumento,
    DocumentoDiaria, DocumentoReembolso, DocumentoJeton, DocumentoAuxilio,
    StatusChoicesVerbasIndenizatorias, StatusChoicesProcesso, TiposDePagamento,
    Processo, Credor, Tabela_Valores_Unitarios_Verbas_Indenizatorias, MeiosDeTransporte,
)
from ..filters import DiariaFilter, ReembolsoFilter, JetonFilter, AuxilioFilter, DiariasAutorizacaoFilter
from ..utils import gerar_pdf_pcd

_EXTENSOES_DOCUMENTO_PERMITIDAS = {'.pdf', '.jpg', '.jpeg', '.png'}


def diarias_list_view(request):
    queryset = Diaria.objects.select_related('beneficiario', 'status', 'processo').all().order_by('-id')
    meu_filtro = DiariaFilter(request.GET, queryset=queryset)
    return render(request, 'verbas/diarias_list.html', {'filter': meu_filtro, 'registros': meu_filtro.qs})


def reembolsos_list_view(request):
    queryset = ReembolsoCombustivel.objects.select_related('beneficiario', 'status', 'processo').all().order_by('-id')
    meu_filtro = ReembolsoFilter(request.GET, queryset=queryset)
    return render(request, 'verbas/reembolsos_list.html', {'filter': meu_filtro, 'registros': meu_filtro.qs})


def jetons_list_view(request):
    queryset = Jeton.objects.select_related('beneficiario', 'status', 'processo').all().order_by('-id')
    meu_filtro = JetonFilter(request.GET, queryset=queryset)
    return render(request, 'verbas/jetons_list.html', {'filter': meu_filtro, 'registros': meu_filtro.qs})


def auxilios_list_view(request):
    queryset = AuxilioRepresentacao.objects.select_related('beneficiario', 'status', 'processo').all().order_by('-id')
    meu_filtro = AuxilioFilter(request.GET, queryset=queryset)
    return render(request, 'verbas/auxilios_list.html', {'filter': meu_filtro, 'registros': meu_filtro.qs})


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
    return render(request, 'verbas/add_diaria.html', {'form': form, 'tipos_documento': tipos_doc})


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
    return render(request, 'verbas/add_reembolso.html', {'form': form, 'tipos_documento': tipos_doc})


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
    return render(request, 'verbas/add_jeton.html', {'form': form, 'tipos_documento': tipos_doc})


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
    return render(request, 'verbas/add_auxilio.html', {'form': form, 'tipos_documento': tipos_doc})


def verbas_panel_view(request):
    return render(request, 'verbas/verbas_panel.html')


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
        tipo_de_pagamento__iexact='VERBAS INDENIZATÓRIAS',
        defaults={'tipo_de_pagamento': 'VERBAS INDENIZATÓRIAS'}
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
    return render(request, 'verbas/editar_processo_verbas.html', context)


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

    _, ext = os.path.splitext(arquivo.name.lower())
    if ext not in _EXTENSOES_DOCUMENTO_PERMITIDAS:
        return JsonResponse({'ok': False, 'error': 'Formato não permitido. Use PDF, JPG ou PNG.'}, status=400)

    try:
        kwargs = {fk_name: verba, 'arquivo': arquivo, 'tipo_id': tipo_id}
        doc = ModeloDocumento.objects.create(**kwargs)
        return JsonResponse({'ok': True, 'doc_id': doc.id, 'arquivo_url': doc.arquivo.url, 'tipo': str(doc.tipo)})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


def gerenciar_diaria_view(request, pk):
    diaria = get_object_or_404(Diaria, id=pk)
    documentos = diaria.documentos.select_related('tipo').all()
    tipos_doc = TiposDeDocumento.objects.filter(is_active=True)

    if request.method == 'POST':
        arquivo = request.FILES.get('arquivo')
        tipo_id = request.POST.get('tipo')
        if arquivo and tipo_id:
            _, ext = os.path.splitext(arquivo.name.lower())
            if ext not in _EXTENSOES_DOCUMENTO_PERMITIDAS:
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
    return render(request, 'verbas/gerenciar_diaria.html', context)


def painel_autorizacao_diarias_view(request):
    queryset_base = Diaria.objects.select_related(
        'beneficiario', 'proponente', 'processo'
    ).all().order_by('-id')

    meu_filtro = DiariasAutorizacaoFilter(request.GET, queryset=queryset_base)

    context = {
        'meu_filtro': meu_filtro,
        'diarias': meu_filtro.qs,
    }
    return render(request, 'verbas/painel_autorizacao_diarias.html', context)


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


def edit_reembolso_view(request, pk):
    reembolso = get_object_or_404(ReembolsoCombustivel, id=pk)
    documentos = reembolso.documentos.select_related('tipo').all()
    tipos_doc = TiposDeDocumento.objects.filter(is_active=True)

    if request.method == 'POST':
        if request.POST.get('upload_doc'):
            arquivo = request.FILES.get('arquivo')
            tipo_id = request.POST.get('tipo')
            if arquivo and tipo_id:
                _, ext = os.path.splitext(arquivo.name.lower())
                if ext not in _EXTENSOES_DOCUMENTO_PERMITIDAS:
                    messages.error(request, 'Formato de arquivo não permitido. Use PDF, JPG ou PNG.')
                else:
                    try:
                        DocumentoReembolso.objects.create(reembolso=reembolso, arquivo=arquivo, tipo_id=tipo_id)
                        messages.success(request, 'Documento anexado com sucesso!')
                    except Exception:
                        messages.error(request, 'Erro ao salvar o documento. Tente novamente.')
            else:
                messages.error(request, 'Selecione um arquivo e um tipo de documento.')
            return redirect('edit_reembolso', pk=reembolso.id)
        else:
            form = ReembolsoForm(request.POST, instance=reembolso)
            if form.is_valid():
                form.save()
                messages.success(request, 'Reembolso atualizado com sucesso!')
                return redirect('edit_reembolso', pk=reembolso.id)
            else:
                messages.error(request, 'Erro ao salvar. Verifique os campos.')
    else:
        form = ReembolsoForm(instance=reembolso)

    context = {
        'reembolso': reembolso,
        'form': form,
        'documentos': documentos,
        'tipos_documento': tipos_doc,
    }
    return render(request, 'verbas/edit_reembolso.html', context)


def edit_jeton_view(request, pk):
    jeton = get_object_or_404(Jeton, id=pk)
    documentos = jeton.documentos.select_related('tipo').all()
    tipos_doc = TiposDeDocumento.objects.filter(is_active=True)

    if request.method == 'POST':
        if request.POST.get('upload_doc'):
            arquivo = request.FILES.get('arquivo')
            tipo_id = request.POST.get('tipo')
            if arquivo and tipo_id:
                _, ext = os.path.splitext(arquivo.name.lower())
                if ext not in _EXTENSOES_DOCUMENTO_PERMITIDAS:
                    messages.error(request, 'Formato de arquivo não permitido. Use PDF, JPG ou PNG.')
                else:
                    try:
                        DocumentoJeton.objects.create(jeton=jeton, arquivo=arquivo, tipo_id=tipo_id)
                        messages.success(request, 'Documento anexado com sucesso!')
                    except Exception:
                        messages.error(request, 'Erro ao salvar o documento. Tente novamente.')
            else:
                messages.error(request, 'Selecione um arquivo e um tipo de documento.')
            return redirect('edit_jeton', pk=jeton.id)
        else:
            form = JetonForm(request.POST, instance=jeton)
            if form.is_valid():
                form.save()
                messages.success(request, 'Jeton atualizado com sucesso!')
                return redirect('edit_jeton', pk=jeton.id)
            else:
                messages.error(request, 'Erro ao salvar. Verifique os campos.')
    else:
        form = JetonForm(instance=jeton)

    context = {
        'jeton': jeton,
        'form': form,
        'documentos': documentos,
        'tipos_documento': tipos_doc,
    }
    return render(request, 'verbas/edit_jeton.html', context)


def edit_auxilio_view(request, pk):
    auxilio = get_object_or_404(AuxilioRepresentacao, id=pk)
    documentos = auxilio.documentos.select_related('tipo').all()
    tipos_doc = TiposDeDocumento.objects.filter(is_active=True)

    if request.method == 'POST':
        if request.POST.get('upload_doc'):
            arquivo = request.FILES.get('arquivo')
            tipo_id = request.POST.get('tipo')
            if arquivo and tipo_id:
                _, ext = os.path.splitext(arquivo.name.lower())
                if ext not in _EXTENSOES_DOCUMENTO_PERMITIDAS:
                    messages.error(request, 'Formato de arquivo não permitido. Use PDF, JPG ou PNG.')
                else:
                    try:
                        DocumentoAuxilio.objects.create(auxilio=auxilio, arquivo=arquivo, tipo_id=tipo_id)
                        messages.success(request, 'Documento anexado com sucesso!')
                    except Exception:
                        messages.error(request, 'Erro ao salvar o documento. Tente novamente.')
            else:
                messages.error(request, 'Selecione um arquivo e um tipo de documento.')
            return redirect('edit_auxilio', pk=auxilio.id)
        else:
            form = AuxilioForm(request.POST, instance=auxilio)
            if form.is_valid():
                form.save()
                messages.success(request, 'Auxílio atualizado com sucesso!')
                return redirect('edit_auxilio', pk=auxilio.id)
            else:
                messages.error(request, 'Erro ao salvar. Verifique os campos.')
    else:
        form = AuxilioForm(instance=auxilio)

    context = {
        'auxilio': auxilio,
        'form': form,
        'documentos': documentos,
        'tipos_documento': tipos_doc,
    }
    return render(request, 'verbas/edit_auxilio.html', context)


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


@login_required
def gerar_pcd_view(request, pk):
    """
    Gera e serve o PDF "Proposta de Concessão de Diárias (PCD)" para a diária indicada.
    """
    diaria = get_object_or_404(Diaria, pk=pk)
    pdf_buffer = gerar_pdf_pcd(diaria)
    nome_arquivo = f"PCD_{diaria.numero_sequencial}.pdf"
    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nome_arquivo}"'
    return response
