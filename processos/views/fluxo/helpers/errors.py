"""Exceções de domínio para helpers do fluxo financeiro."""


class ArquivamentoDefinitivoError(Exception):
    """Erro de domínio para falhas no arquivamento definitivo."""


class ArquivamentoSemDocumentosError(ArquivamentoDefinitivoError):
    """Indica ausência de documentos válidos para gerar o consolidado."""


__all__ = [
    "ArquivamentoDefinitivoError",
    "ArquivamentoSemDocumentosError",
]
