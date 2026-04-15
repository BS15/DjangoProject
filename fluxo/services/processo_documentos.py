"""Document services for the Processo aggregate (standardized as 'documents')."""

import logging
import os

from commons.shared.document_services import obter_ou_criar_tipo_documento, obter_proxima_ordem_documento
from commons.shared.pdf_tools import PdfMergeError, mesclar_pdfs_em_memoria
from commons.shared.pdf_response import gerar_documento_bytes
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from fluxo.pdf_generators import FLUXO_DOCUMENT_REGISTRY

logger = logging.getLogger(__name__)

class DocumentoGeradoDuplicadoError(Exception):
    """Documento automático já existente para o processo e nome informado."""


def gerar_pdf_consolidado_processo(processo):
    """Mescla documentos do processo por ordem e retorna PDF em memória."""
    lista_caminhos = []
    for doc in processo.documentos.order_by("ordem"):
        if doc.arquivo and doc.arquivo.name and os.path.exists(doc.arquivo.path):
            lista_caminhos.append(doc.arquivo.path)
    if not lista_caminhos:
        return None
    try:
        return mesclar_pdfs_em_memoria(lista_caminhos)
    except PdfMergeError as exc:
        logger.exception("Falha ao gerar PDF consolidado do processo %s", processo.id)
        raise RuntimeError(f"Falha técnica ao consolidar PDFs do processo {processo.id}.") from exc

def anexar_pdf_gerado_ao_processo(processo, pdf_bytes, nome_arquivo, tipo_documento_nome):
    """Anexa PDF gerado como Boleto_Bancario na próxima ordem disponível."""
    from fluxo.domain_models import Boleto_Bancario
    if processo.documentos.filter(arquivo__icontains=nome_arquivo).exists():
        raise ValidationError(f"Documento automático já existe para o processo {processo.id}: {nome_arquivo}")
    proxima_ordem = obter_proxima_ordem_documento(processo.documentos)
    tipo_documento = obter_ou_criar_tipo_documento(
        tipo_documento_nome,
        tipo_pagamento=processo.tipo_pagamento if processo.tipo_pagamento_id else None,
    )
    Boleto_Bancario.objects.create(
        processo=processo,
        arquivo=ContentFile(pdf_bytes, name=nome_arquivo),
        tipo=tipo_documento,
        ordem=proxima_ordem,
    )
    return True

def gerar_e_anexar_documento_processo(processo, doc_type, obj, nome_arquivo, tipo_documento_nome, **kwargs):
    """Gera PDF e anexa ao processo com proteção de duplicidade por nome."""
    if processo.documentos.filter(arquivo__icontains=nome_arquivo).exists():
        raise DocumentoGeradoDuplicadoError(
            f"Documento automático já existe no processo #{processo.id}: {nome_arquivo}"
        )
    pdf_bytes = gerar_documento_bytes(doc_type, obj, FLUXO_DOCUMENT_REGISTRY, **kwargs)
    return anexar_pdf_gerado_ao_processo(processo, pdf_bytes, nome_arquivo, tipo_documento_nome)

def gerar_anexo_por_tipo(processo, doc_type, obj, nome_arquivo, tipo_documento_nome, **kwargs):
    """Gera PDF via engine e anexa ao processo sem duplicar arquivo."""
    try:
        return gerar_e_anexar_documento_processo(
            processo,
            doc_type,
            obj,
            nome_arquivo,
            tipo_documento_nome,
            **kwargs,
        )
    except DocumentoGeradoDuplicadoError:
        logger.info(
            "Documento automático duplicado ignorado no processo %s: %s",
            processo.id,
            nome_arquivo,
        )
        return None

def gerar_documentos_automaticos_processo(processo, status_anterior, novo_status):
    """Gera e anexa documentos automáticos conforme transição do processo."""
    from fluxo.services.integracoes.processo_relacionados import gerar_documentos_relacionados_por_transicao
    try:
        if novo_status == "A PAGAR - AUTORIZADO":
            gerar_anexo_por_tipo(
                processo,
                "autorizacao",
                processo,
                f"Termo_Autorizacao_Proc_{processo.id}.pdf",
                "TERMO DE AUTORIZAÇÃO DE PAGAMENTO",
            )
        if novo_status == "CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL":
            gerar_anexo_por_tipo(
                processo,
                "contabilizacao",
                processo,
                f"Termo_Contabilizacao_Proc_{processo.id}.pdf",
                "TERMO DE CONTABILIZAÇÃO",
            )
            gerar_anexo_por_tipo(
                processo,
                "auditoria",
                processo,
                f"Termo_Auditoria_Proc_{processo.id}.pdf",
                "TERMO DE AUDITORIA",
            )
    except Exception as exc:
        logger.exception("Erro ao gerar documentos automáticos para o processo %s", processo.id)
        raise
