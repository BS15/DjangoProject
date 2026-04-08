"""Exceções de domínio para importação/sincronização de diárias."""


class DiariaCsvValidationError(ValueError):
    """Erro de validação de linha no CSV de diárias."""


__all__ = ["DiariaCsvValidationError"]
