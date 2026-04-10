"""Logica de arquivamento definitivo de processos."""

import logging

from django.core.files.base import ContentFile
from django.db import transaction

from .errors import ArquivamentoDefinitivoError, ArquivamentoSemDocumentosError


logger = logging.getLogger(__name__)


def _executar_arquivamento_definitivo(processo, usuario):
    """Gera o PDF consolidado final e arquiva definitivamente o processo.

    O arquivo é salvo no próprio processo e a mudança para o status
    ``ARQUIVADO`` só ocorre se toda a operação for concluída com sucesso.
    """
    pdf_buffer = processo.gerar_pdf_consolidado()
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
        processo.avancar_status("ARQUIVADO", usuario=usuario)

    return True


__all__ = [
    "_executar_arquivamento_definitivo",
]
