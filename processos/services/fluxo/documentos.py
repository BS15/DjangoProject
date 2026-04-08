"""Operações documentais específicas do fluxo de processos."""

from ..shared.documentos import gerar_documento_bytes
from .errors import DocumentoGeradoDuplicadoError


def gerar_e_anexar_documento_processo(processo, doc_type, obj, nome_arquivo, tipo_documento_nome, **kwargs):
    """Gera PDF e anexa ao processo com proteção de duplicidade por nome."""
    if processo.documentos.filter(arquivo__icontains=nome_arquivo).exists():
        raise DocumentoGeradoDuplicadoError(
            f"Documento automático já existe no processo #{processo.id}: {nome_arquivo}"
        )

    pdf_bytes = gerar_documento_bytes(doc_type, obj, **kwargs)
    return processo._anexar_pdf_gerado(pdf_bytes, nome_arquivo, tipo_documento_nome)


__all__ = [
    'gerar_e_anexar_documento_processo',
]