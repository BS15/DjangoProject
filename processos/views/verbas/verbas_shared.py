import os
from django.shortcuts import render
from django.contrib import messages
from django.db.models import Max
from django.core.files.base import ContentFile

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


def _get_tipos_documento_ativos():
    return TiposDeDocumento.objects.filter(is_active=True)


def _extensao_documento_permitida(nome_arquivo):
    _, ext = os.path.splitext(nome_arquivo.lower())
    return ext in _EXTENSOES_DOCUMENTO_PERMITIDAS


def _anexar_documento(modelo_documento, fk_name, entidade, arquivo, tipo_id):
    kwargs = {fk_name: entidade, 'arquivo': arquivo, 'tipo_id': tipo_id}
    return modelo_documento.objects.create(**kwargs)


def _processar_upload_documento(request, entidade, modelo_documento, fk_name):
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
    beneficiario_ids = {item.beneficiario_id for item in itens if item.beneficiario_id}
    if len(beneficiario_ids) <= 1:
        return next((item.beneficiario for item in itens if item.beneficiario_id), None)

    credor_banco, _ = Credor.objects.get_or_create(
        nome__iexact=_CREDOR_AGRUPAMENTO_MULTIPLO,
        defaults={'nome': _CREDOR_AGRUPAMENTO_MULTIPLO, 'tipo': 'PJ'},
    )
    return credor_banco


def _anexar_scd_na_diaria(diaria, pdf_bytes):
    tipo_scd, _ = TiposDeDocumento.objects.get_or_create(
        tipo_de_documento__iexact='SOLICITAÇÃO DE CONCESSÃO DE DIÁRIAS (SCD)',
        defaults={'tipo_de_documento': 'SOLICITAÇÃO DE CONCESSÃO DE DIÁRIAS (SCD)'},
    )
    proxima_ordem = (diaria.documentos.aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1
    DocumentoDiaria.objects.create(
        diaria=diaria,
        arquivo=ContentFile(pdf_bytes, name=f"SCD_{diaria.id}.pdf"),
        tipo=tipo_scd,
        ordem=proxima_ordem,
    )
