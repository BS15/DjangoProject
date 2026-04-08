"""Exceções de domínio para utilitários compartilhados."""


class PdfMergeError(Exception):
    """Erro ao mesclar arquivos PDF em memória."""


__all__ = ["PdfMergeError"]
