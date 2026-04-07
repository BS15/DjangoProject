import os
from django.db import transaction
from django.shortcuts import render
from django.contrib import messages

from ..shared import render_filtered_list
from ...models import (
    Diaria,
    ReembolsoCombustivel,
    Jeton,
    AuxilioRepresentacao,
    TiposDeDocumento,
    DocumentoDiaria,
    DocumentoReembolso,
    DocumentoJeton,
    DocumentoAuxilio,
    Credor,
)

_EXTENSOES_DOCUMENTO_PERMITIDAS = {'.pdf', '.jpg', '.jpeg', '.png'}
_CREDOR_AGRUPAMENTO_MULTIPLO = 'BANCO DO BRASIL S/A'

_VERBA_CONFIG = {
    'diaria': {
        'model': Diaria,
        'list_url': 'diarias_list',
        'doc_model': DocumentoDiaria,
        'doc_fk': 'diaria',
        'doc_tipo_seguro': 'verba_diaria_doc',
    },
    'reembolso': {
        'model': ReembolsoCombustivel,
        'list_url': 'reembolsos_list',
        'doc_model': DocumentoReembolso,
        'doc_fk': 'reembolso',
        'doc_tipo_seguro': 'verba_reembolso_doc',
    },
    'jeton': {
        'model': Jeton,
        'list_url': 'jetons_list',
        'doc_model': DocumentoJeton,
        'doc_fk': 'jeton',
        'doc_tipo_seguro': 'verba_jeton_doc',
    },
    'auxilio': {
        'model': AuxilioRepresentacao,
        'list_url': 'auxilios_list',
        'doc_model': DocumentoAuxilio,
        'doc_fk': 'auxilio',
        'doc_tipo_seguro': 'verba_auxilio_doc',
    },
}

_VERBA_PERMISSION_MAP = {
    'diaria': 'processos.pode_gerenciar_diarias',
    'reembolso': 'processos.pode_gerenciar_reembolsos',
    'jeton': 'processos.pode_gerenciar_jetons',
    'auxilio': 'processos.pode_gerenciar_auxilios',
}


def _get_tipos_documento_ativos():
    """Retorna os tipos de documento ativos disponíveis para anexação."""
    return TiposDeDocumento.objects.filter(is_active=True)


def _get_permissao_gestao_verba(tipo_verba):
    """Resolve a permissão Django necessária para gerenciar o tipo de verba."""
    return _VERBA_PERMISSION_MAP.get(tipo_verba)


def _extensao_documento_permitida(nome_arquivo):
    """Valida se a extensão do arquivo está entre os formatos permitidos."""
    _, ext = os.path.splitext(nome_arquivo.lower())
    return ext in _EXTENSOES_DOCUMENTO_PERMITIDAS


def _anexar_documento(modelo_documento, fk_name, entidade, arquivo, tipo_id):
    """Cria o registro de documento vinculado à entidade de verba informada."""
    kwargs = {fk_name: entidade, 'arquivo': arquivo, 'tipo_id': tipo_id}
    return modelo_documento.objects.create(**kwargs)


def _obter_dados_upload_documento(request, *, arquivo_field='arquivo', tipo_field='tipo'):
    """Extrai arquivo e tipo documental do payload da requisição."""
    return request.FILES.get(arquivo_field), request.POST.get(tipo_field)


def _validar_upload_documento(arquivo, tipo_id, *, obrigatorio=True):
    """Valida presença e extensão do upload documental."""
    if not arquivo and not tipo_id and not obrigatorio:
        return None

    if not arquivo or not tipo_id:
        return 'Selecione um arquivo e um tipo de documento.'

    if not _extensao_documento_permitida(arquivo.name):
        return 'Formato de arquivo não permitido. Use PDF, JPG ou PNG.'

    return None


def _salvar_documento_upload(
    entidade,
    *,
    modelo_documento,
    fk_name,
    arquivo,
    tipo_id,
    obrigatorio=True,
):
    """Valida e persiste um documento de verba, retornando `(documento, erro)` ."""
    erro = _validar_upload_documento(arquivo, tipo_id, obrigatorio=obrigatorio)
    if erro:
        return None, erro

    if not arquivo:
        return None, None

    try:
        return _anexar_documento(modelo_documento, fk_name, entidade, arquivo, tipo_id), None
    except Exception:
        return None, 'Erro ao salvar o documento. Tente novamente.'


def _processar_upload_documento(request, entidade, modelo_documento, fk_name):
    """Processa upload de documento, valida entrada e persiste o anexo."""
    arquivo, tipo_id = _obter_dados_upload_documento(request)
    _, erro = _salvar_documento_upload(
        entidade,
        modelo_documento=modelo_documento,
        fk_name=fk_name,
        arquivo=arquivo,
        tipo_id=tipo_id,
    )
    if erro:
        messages.error(request, erro)
        return False

    messages.success(request, 'Documento anexado com sucesso!')
    return True


def _render_lista_verba(request, model, filter_class, template_name):
    """Renderiza listagem filtrável padrão para módulos de verbas indenizatórias."""
    queryset = model.objects.select_related('beneficiario', 'status', 'processo').order_by('-id')
    return render_filtered_list(
        request,
        queryset=queryset,
        filter_class=filter_class,
        template_name=template_name,
        items_key='registros',
        filter_key='filter',
    )


def _obter_credor_agrupamento(itens):
    """Obtém o credor de agrupamento para lote, criando credor padrão quando necessário."""
    beneficiario_ids = {item.beneficiario_id for item in itens if item.beneficiario_id}
    if len(beneficiario_ids) <= 1:
        return next((item.beneficiario for item in itens if item.beneficiario_id), None)

    credor_banco, _ = Credor.objects.get_or_create(
        nome__iexact=_CREDOR_AGRUPAMENTO_MULTIPLO,
        defaults={'nome': _CREDOR_AGRUPAMENTO_MULTIPLO, 'tipo': 'PJ'},
    )
    return credor_banco


def _salvar_verba_com_anexo_opcional(
    request,
    *,
    form,
    modelo_documento,
    fk_name,
    pre_save=None,
    post_save=None,
):
    """Salva uma verba e anexa documento opcional em transação atômica."""
    arquivo, tipo_id = _obter_dados_upload_documento(
        request,
        arquivo_field='documento_anexo',
        tipo_field='tipo_documento_anexo',
    )
    erro = _validar_upload_documento(arquivo, tipo_id, obrigatorio=False)
    if erro:
        messages.error(request, erro)
        return None

    with transaction.atomic():
        instancia = form.save(commit=False)
        if pre_save:
            pre_save(instancia)
        instancia.save()

        if hasattr(form, 'save_m2m'):
            form.save_m2m()

        if post_save:
            post_save(instancia)

        if arquivo:
            _anexar_documento(modelo_documento, fk_name, instancia, arquivo, tipo_id)

    return instancia


def _processar_edicao_verba_com_upload(
    request,
    *,
    instancia,
    form_class,
    modelo_documento,
    fk_name,
    success_message,
):
    """Processa fluxo padrao de edicao com upload avulso de documento."""
    if request.method == 'POST' and request.POST.get('upload_doc'):
        _processar_upload_documento(request, instancia, modelo_documento, fk_name)
        return None, True

    if request.method == 'POST':
        form = form_class(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            messages.success(request, success_message)
            return None, True
        messages.error(request, 'Erro ao salvar. Verifique os campos.')
        return form, False

    return form_class(instance=instancia), False
