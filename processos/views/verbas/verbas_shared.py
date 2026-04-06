import os
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


def _processar_upload_documento(request, entidade, modelo_documento, fk_name):
    """Processa upload de documento, valida entrada e persiste o anexo."""
    arquivo = request.FILES.get('arquivo')
    tipo_id = request.POST.get('tipo')
    if not arquivo or not tipo_id:
        messages.error(request, 'Selecione um arquivo e um tipo de documento.')
        return False

    if not _extensao_documento_permitida(arquivo.name):
        messages.error(request, 'Formato de arquivo não permitido. Use PDF, JPG ou PNG.')
        return False

    try:
        _anexar_documento(modelo_documento, fk_name, entidade, arquivo, tipo_id)
        messages.success(request, 'Documento anexado com sucesso!')
        return True
    except Exception:
        messages.error(request, 'Erro ao salvar o documento. Tente novamente.')
        return False


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
