"""Exceções de domínio para serviços do fluxo de pagamentos."""


class DocumentoGeradoDuplicadoError(Exception):
    """Documento automático já existente para o processo e nome informado."""


__all__ = ["DocumentoGeradoDuplicadoError"]
