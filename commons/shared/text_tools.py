"""Utilitários transversais de normalização e formatação."""

import logging
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation


logger = logging.getLogger(__name__)


def _digits_only(value):
    return re.sub(r"\D", "", value or "")


def normalize_text(value, *, collapse_spaces=True):
    if not value:
        return ""

    normalized = unicodedata.normalize("NFD", value.upper())
    no_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    if not collapse_spaces:
        return no_accents.strip()
    return re.sub(r"\s+", " ", no_accents).strip()


def normalize_document(value):
    return _digits_only(value)


def normalize_account(agencia, conta):
    agencia_norm = (agencia or "").strip().replace(" ", "")
    conta_norm = (conta or "").strip().replace(" ", "").replace(".", "")
    return agencia_norm.upper(), conta_norm.upper()


def normalize_name_for_match(value):
    return normalize_text(value)


def names_bidirectional_match(left, right):
    left_norm = normalize_name_for_match(left)
    right_norm = normalize_name_for_match(right)
    if not left_norm or not right_norm:
        return False
    return left_norm in right_norm or right_norm in left_norm


def decimals_equal_money(left, right):
    if left is None or right is None:
        return False
    return Decimal(left).quantize(Decimal("0.01")) == Decimal(right).quantize(Decimal("0.01"))


def normalize_choice(value, valid_choices, default=""):
    return value if value in valid_choices else default


def format_br_date(value, empty_value="-"):
    return value.strftime("%d/%m/%Y") if value else empty_value


def format_brl_currency(value, empty_value="-"):
    if value is None:
        return empty_value

    parsed_value = parse_brl_decimal(value, default=None)
    if parsed_value is None:
        return empty_value

    int_part, dec_part = f"{abs(parsed_value):.2f}".split(".")
    int_formatted = "{:,}".format(int(int_part)).replace(",", ".")
    signal = "-" if parsed_value < 0 else ""
    return f"R$ {signal}{int_formatted},{dec_part}"


def format_brl_amount(value, empty_value="-", include_symbol=False):
    formatted = format_brl_currency(value, empty_value=empty_value)
    if formatted == empty_value or include_symbol:
        return formatted
    return formatted.removeprefix("R$ ")


def parse_brl_decimal(value, default=None):
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
    except (InvalidOperation, ValueError) as exc:
        logger.warning("evento=erro_parse_decimal_brl valor=%s erro=%s", value, exc)
        return default


def parse_br_date(date_str):
    try:
        if not date_str:
            return None
        return datetime.strptime(date_str.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError as exc:
        logger.warning("evento=erro_parse_data_br valor=%s erro=%s", date_str, exc)
        return None
