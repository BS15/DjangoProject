"""Utilitários compartilhados entre múltiplos apps."""

from .access_utils import user_is_entity_owner
from .pdf_response import gerar_documento_bytes, gerar_resposta_pdf, montar_resposta_pdf
from .signature_services import (
    AssinaturaSignatariosError,
    criar_assinatura_rascunho,
    disparar_assinatura_rascunho_com_signatarios,
)
from .text_tools import (
    decimals_equal_money,
    format_br_date,
    format_brl_amount,
    format_brl_currency,
    names_bidirectional_match,
    normalize_account,
    normalize_choice,
    normalize_document,
    normalize_name_for_match,
    normalize_text,
    parse_br_date,
    parse_brl_decimal,
)

__all__ = [
    "user_is_entity_owner",
    "gerar_documento_bytes",
    "gerar_resposta_pdf",
    "montar_resposta_pdf",
    "AssinaturaSignatariosError",
    "criar_assinatura_rascunho",
    "disparar_assinatura_rascunho_com_signatarios",
    "decimals_equal_money",
    "format_br_date",
    "format_brl_amount",
    "format_brl_currency",
    "names_bidirectional_match",
    "normalize_account",
    "normalize_choice",
    "normalize_document",
    "normalize_name_for_match",
    "normalize_text",
    "parse_br_date",
    "parse_brl_decimal",
]
