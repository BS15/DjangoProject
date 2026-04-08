"""Utilitários puros para normalização e formatação de texto e valores.

Consolidação de todas as operações determinísticas de transformação de strings,
datas e números. Não acessa banco de dados nem processamento de PDF.

Módulo canônico: use este ao invés de processos.utils.text_helpers
"""

import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation


def _digits_only(value):
    """Retorna apenas dígitos de ``value`` para comparações determinísticas."""
    return re.sub(r"\D", "", value or "")


def normalize_text(value, *, collapse_spaces=True):
    """Normaliza texto removendo acentos e padronizando caixa e espaçamento."""
    if not value:
        return ""

    normalized = unicodedata.normalize("NFD", value.upper())
    no_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    if not collapse_spaces:
        return no_accents.strip()
    return re.sub(r"\s+", " ", no_accents).strip()


def normalize_document(value):
    """Normaliza CPF/CNPJ para string numérica sem máscara."""
    return _digits_only(value)


def normalize_account(agencia, conta):
    """Normaliza agência e conta para comparação robusta de dados bancários."""
    agencia_norm = (agencia or "").strip().replace(" ", "")
    conta_norm = (conta or "").strip().replace(" ", "").replace(".", "")
    return agencia_norm.upper(), conta_norm.upper()


def normalize_name_for_match(value):
    """Normaliza nomes removendo acentos e padronizando caixa/espaços."""
    return normalize_text(value)


def names_bidirectional_match(left, right):
    """Retorna verdadeiro quando um nome contém o outro após normalização."""
    left_norm = normalize_name_for_match(left)
    right_norm = normalize_name_for_match(right)
    if not left_norm or not right_norm:
        return False
    return left_norm in right_norm or right_norm in left_norm


def decimals_equal_money(left, right):
    """Compara dois valores monetários com precisão de centavos."""
    if left is None or right is None:
        return False
    return Decimal(left).quantize(Decimal("0.01")) == Decimal(right).quantize(Decimal("0.01"))


def normalize_choice(value, valid_choices, default=""):
    """Retorna o valor quando válido ou aplica valor padrão para opções inválidas."""
    return value if value in valid_choices else default


def format_br_date(value, empty_value="-"):
    """Formata data em DD/MM/AAAA para exibição em interface."""
    return value.strftime("%d/%m/%Y") if value else empty_value


def format_brl_currency(value, empty_value="-"):
    """Formata valor no padrão monetário brasileiro com símbolo de real."""
    if value is None:
        return empty_value

    int_part, dec_part = f"{abs(value):.2f}".split(".")
    int_formatted = "{:,}".format(int(int_part)).replace(",", ".")
    signal = "-" if value < 0 else ""
    return f"R$ {signal}{int_formatted},{dec_part}"


def format_brl_amount(value, empty_value="-", include_symbol=False):
    """Formata valor no padrão brasileiro com símbolo opcional."""
    formatted = format_brl_currency(value, empty_value=empty_value)
    if formatted == empty_value or include_symbol:
        return formatted
    return formatted.removeprefix("R$ ")


def parse_brl_decimal(value, default=None):
    """Converte texto numérico brasileiro em Decimal com tratamento tolerante."""
    if value is None:
        return default

    if isinstance(value, Decimal):
        return value

    normalized = str(value).strip()
    if not normalized:
        return default

    normalized = normalized.replace("R$", "").replace(" ", "")
    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")

    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError):
        return default


def safe_split(line, keyword, index=1):
    """Divide uma linha por palavra-chave e retorna parte indexada com segurança."""
    parts = line.split(keyword)
    if len(parts) > index:
        return parts[index].strip()
    return ""


def parse_br_date(date_str):
    """Converte data no formato DD/MM/AAAA para AAAA-MM-DD."""
    try:
        if not date_str:
            return None
        return datetime.strptime(date_str.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def extract_text_between(full_text, start_anchor, end_anchor):
    """Extrai trecho entre âncoras de início e fim com fallback para quebra de linha."""
    if full_text is None:
        return ""

    start_idx = full_text.find(start_anchor)
    if start_idx == -1:
        return ""

    start_idx += len(start_anchor)
    end_idx = full_text.find(end_anchor, start_idx)
    if end_idx == -1:
        end_idx = full_text.find("\n", start_idx)

    return full_text[start_idx:end_idx].replace("\n", "").strip()


__all__ = [
    "normalize_document",
    "normalize_account",
    "normalize_text",
    "normalize_name_for_match",
    "names_bidirectional_match",
    "decimals_equal_money",
    "normalize_choice",
    "format_br_date",
    "format_brl_currency",
    "format_brl_amount",
    "parse_brl_decimal",
    "safe_split",
    "parse_br_date",
    "extract_text_between",
]
