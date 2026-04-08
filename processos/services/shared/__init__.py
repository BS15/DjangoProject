"""Services compartilhados entre workflows."""

from .documentos import (
    construir_signatarios_padrao,
    criar_assinatura_rascunho,
    disparar_assinatura_rascunho,
    disparar_assinatura_rascunho_com_signatarios,
    enviar_para_assinatura,
    gerar_documento_bytes,
    gerar_resposta_pdf,
    montar_resposta_pdf,
    sincronizar_assinatura,
)
from .errors import AssinaturaSignatariosError

__all__ = [
    'AssinaturaSignatariosError',
    'construir_signatarios_padrao',
    'criar_assinatura_rascunho',
    'disparar_assinatura_rascunho',
    'disparar_assinatura_rascunho_com_signatarios',
    'enviar_para_assinatura',
    'gerar_documento_bytes',
    'gerar_resposta_pdf',
    'montar_resposta_pdf',
    'sincronizar_assinatura',
]