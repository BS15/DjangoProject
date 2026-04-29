"""Utilitários compartilhados entre múltiplos apps."""

from .access_utils import user_is_entity_owner
from .pdf_response import gerar_documento_bytes, gerar_resposta_pdf, montar_resposta_pdf
from .signature_services import (
    AssinaturaSignatariosError,
    criar_assinatura_rascunho,
    disparar_assinatura_rascunho_com_signatarios,
)
from .query_tools import (
    aplicar_filtro_por_opcao,
    obter_campo_ordenacao,
    resolver_parametros_ordenacao,
)
from .text_tools import (
    decimals_equal_money,
    format_br_date,
    format_brl_amount,
    format_brl_currency,
    names_bidirectional_match,
    normalize_account,
    normalize_choice,
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
    "aplicar_filtro_por_opcao",
    "obter_campo_ordenacao",
    "resolver_parametros_ordenacao",
    "decimals_equal_money",
    "format_br_date",
    "format_brl_amount",
    "format_brl_currency",
    "names_bidirectional_match",
    "normalize_account",
    "normalize_choice",
    "normalize_text",
    "parse_br_date",
    "parse_brl_decimal",
]
