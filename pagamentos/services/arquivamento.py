"""Serviços canônicos de arquivamento definitivo de processos."""

import logging

from django.core.files.base import ContentFile
from django.db import transaction

from pagamentos.domain_models import ProcessoStatus
from pagamentos.services.processo_documentos import gerar_pdf_consolidado_processo
from pagamentos.views.helpers.errors import ArquivamentoDefinitivoError, ArquivamentoSemDocumentosError


logger = logging.getLogger(__name__)


def executar_arquivamento_definitivo(processo, usuario):
    """Gera o PDF consolidado final e arquiva definitivamente o processo."""
    pdf_buffer = gerar_pdf_consolidado_processo(processo)
    if pdf_buffer is None:
        raise ArquivamentoSemDocumentosError(
            f"Processo #{processo.id} sem documentos válidos para consolidar."
        )

    try:
        pdf_bytes = pdf_buffer.read()
    except (AttributeError, OSError, ValueError) as exc:
        logger.exception("Falha ao ler PDF consolidado do processo %s", processo.id)
        raise ArquivamentoDefinitivoError("Falha ao ler PDF consolidado para arquivamento.") from exc

    if not pdf_bytes:
        raise ArquivamentoDefinitivoError(
            f"Processo #{processo.id} gerou consolidado vazio."
        )

    nome_arquivo = f"processo_{processo.id}_consolidado.pdf"

    with transaction.atomic():
        processo.arquivo_final.save(nome_arquivo, ContentFile(pdf_bytes), save=False)
        processo.save(update_fields=["arquivo_final"])
        processo.avancar_status(ProcessoStatus.ARQUIVADO, usuario=usuario)

    return True


__all__ = ["executar_arquivamento_definitivo"]