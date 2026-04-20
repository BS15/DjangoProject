"""Document services for the Processo aggregate (standardized as 'documents')."""

import logging
from pathlib import PurePosixPath

from commons.shared.document_services import obter_ou_criar_tipo_documento, obter_proxima_ordem_documento
from commons.shared.pdf_tools import PdfMergeError, mesclar_pdfs_em_memoria
from commons.shared.pdf_response import gerar_documento_bytes
from commons.shared.storage_utils import _safe_filename
from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from pagamentos.pdf_generators import FLUXO_DOCUMENT_REGISTRY
from pagamentos.domain_models.processos import ProcessoStatus
from pagamentos.services.integracoes.processo_relacionados import gerar_documentos_relacionados_por_transicao

logger = logging.getLogger(__name__)

class DocumentoGeradoDuplicadoError(Exception):
    """Documento automático já existente para o processo e nome informado."""


def _nomes_documentais_equivalentes(nome_salvo, nome_esperado):
    """Compara o nome lógico ignorando o sufixo que o storage pode adicionar."""
    salvo = PurePosixPath(nome_salvo or "").name
    esperado = _safe_filename(nome_esperado)

    if not salvo or not esperado:
        return False

    salvo_path = PurePosixPath(salvo)
    esperado_path = PurePosixPath(esperado)

    if salvo_path.name.lower() == esperado_path.name.lower():
        return True

    return (
        salvo_path.suffix.lower() == esperado_path.suffix.lower()
        and salvo_path.stem.lower().startswith(f"{esperado_path.stem.lower()}_")
    )


def _documento_automatico_ja_existe(processo, nome_arquivo):
    """Compara pelo basename normalizado para evitar falsos negativos do storage."""
    for documento in processo.documentos.only("arquivo"):
        if _nomes_documentais_equivalentes(documento.arquivo.name, nome_arquivo):
            return True
    return False


def gerar_pdf_consolidado_processo(processo):
    """Mescla documentos do processo por ordem e retorna PDF em memória."""
    arquivos_em_memoria = []
    for doc in processo.documentos.order_by("ordem"):
        if doc.arquivo and doc.arquivo.name and doc.arquivo.storage.exists(doc.arquivo.name):
            with doc.arquivo.open("rb") as arquivo:
                arquivos_em_memoria.append(arquivo.read())
    if not arquivos_em_memoria:
        return None
    try:
        return mesclar_pdfs_em_memoria(arquivos_em_memoria)
    except PdfMergeError as exc:
        logger.exception("Falha ao gerar PDF consolidado do processo %s", processo.id)
        raise RuntimeError(f"Falha técnica ao consolidar PDFs do processo {processo.id}.") from exc

def anexar_pdf_gerado_ao_processo(processo, pdf_bytes, nome_arquivo, tipo_documento_nome):
    """Anexa PDF gerado como DocumentoProcesso na próxima ordem disponível."""
    DocumentoProcesso = apps.get_model("pagamentos", "DocumentoProcesso")
    if _documento_automatico_ja_existe(processo, nome_arquivo):
        raise ValidationError(f"Documento automático já existe para o processo {processo.id}: {nome_arquivo}")
    proxima_ordem = obter_proxima_ordem_documento(processo.documentos)
    tipo_documento = obter_ou_criar_tipo_documento(
        tipo_documento_nome,
        tipo_pagamento=processo.tipo_pagamento if processo.tipo_pagamento_id else None,
    )
    DocumentoProcesso.objects.create(
        processo=processo,
        arquivo=ContentFile(pdf_bytes, name=nome_arquivo),
        tipo=tipo_documento,
        ordem=proxima_ordem,
    )
    return True

def gerar_e_anexar_documento_processo(processo, doc_type, obj, nome_arquivo, tipo_documento_nome, **kwargs):
    """Gera PDF e anexa ao processo com proteção de duplicidade por nome."""
    if _documento_automatico_ja_existe(processo, nome_arquivo):
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
    try:
        if novo_status == ProcessoStatus.A_PAGAR_AUTORIZADO:
            gerar_anexo_por_tipo(
                processo,
                "autorizacao",
                processo,
                f"Termo_Autorizacao_Proc_{processo.id}.pdf",
                "TERMO DE AUTORIZAÇÃO DE PAGAMENTO",
            )
        if novo_status == ProcessoStatus.CONTABILIZADO_CONSELHO:
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
        gerar_documentos_relacionados_por_transicao(processo, status_anterior, novo_status)
    except Exception as exc:
        logger.exception("Erro ao gerar documentos automáticos para o processo %s", processo.id)
        raise
