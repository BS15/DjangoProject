"""Services de integrações externas."""

from .autentique import enviar_documento_para_assinatura, verificar_e_baixar_documento

__all__ = ['enviar_documento_para_assinatura', 'verificar_e_baixar_documento']