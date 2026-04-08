"""Exceções de domínio para serviços compartilhados."""


class AssinaturaSignatariosError(ValueError):
    """Erro ao resolver signatários para disparo de assinatura."""


__all__ = ["AssinaturaSignatariosError"]
