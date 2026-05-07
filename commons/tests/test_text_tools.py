"""Testes unitários para commons/shared/text_tools.py."""

from datetime import date
from decimal import Decimal

import pytest

from commons.shared.text_tools import (
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


# --- normalize_text ---

def test_normalize_text_uppercases_and_removes_accents():
    assert normalize_text("São Paulo") == "SAO PAULO"


def test_normalize_text_collapses_spaces():
    assert normalize_text("  dois   espacos  ") == "DOIS ESPACOS"


def test_normalize_text_no_collapse():
    result = normalize_text("  dois   espacos  ", collapse_spaces=False)
    assert result == "DOIS   ESPACOS"


def test_normalize_text_empty_returns_empty():
    assert normalize_text("") == ""
    assert normalize_text(None) == ""


def test_normalize_text_keeps_numbers_and_special_chars():
    assert normalize_text("abc 123!") == "ABC 123!"


# --- normalize_account ---

def test_normalize_account_strips_whitespace():
    agencia, conta = normalize_account("  0001  ", "  12345-6  ")
    assert agencia == "0001"
    assert conta == "12345-6"


def test_normalize_account_removes_dots_from_conta():
    _, conta = normalize_account("001", "1.234.567-8")
    assert conta == "1234567-8"


def test_normalize_account_uppercases():
    agencia, conta = normalize_account("abc", "xyz")
    assert agencia == "ABC"
    assert conta == "XYZ"


def test_normalize_account_handles_none():
    agencia, conta = normalize_account(None, None)
    assert agencia == ""
    assert conta == ""


# --- names_bidirectional_match ---

def test_names_bidirectional_match_left_in_right():
    assert names_bidirectional_match("João Silva", "João Silva da Costa") is True


def test_names_bidirectional_match_right_in_left():
    assert names_bidirectional_match("João Silva da Costa", "João Silva") is True


def test_names_bidirectional_match_no_match():
    assert names_bidirectional_match("Maria", "José") is False


def test_names_bidirectional_match_empty_left():
    assert names_bidirectional_match("", "José") is False


def test_names_bidirectional_match_empty_right():
    assert names_bidirectional_match("Maria", "") is False


def test_names_bidirectional_match_normalizes_accents():
    assert names_bidirectional_match("joao", "JOÃO SILVA") is True


# --- decimals_equal_money ---

def test_decimals_equal_money_equal():
    assert decimals_equal_money(Decimal("100.00"), Decimal("100.00")) is True


def test_decimals_equal_money_unequal():
    assert decimals_equal_money(Decimal("100.00"), Decimal("100.01")) is False


def test_decimals_equal_money_rounded():
    assert decimals_equal_money(Decimal("100.001"), Decimal("100.00")) is True


def test_decimals_equal_money_none_left():
    assert decimals_equal_money(None, Decimal("100.00")) is False


def test_decimals_equal_money_none_right():
    assert decimals_equal_money(Decimal("100.00"), None) is False


# --- normalize_choice ---

def test_normalize_choice_valid():
    assert normalize_choice("A", ["A", "B", "C"]) == "A"


def test_normalize_choice_invalid():
    assert normalize_choice("Z", ["A", "B", "C"]) == ""


def test_normalize_choice_custom_default():
    assert normalize_choice("Z", ["A", "B"], default="A") == "A"


# --- format_br_date ---

def test_format_br_date_formats_correctly():
    assert format_br_date(date(2026, 4, 15)) == "15/04/2026"


def test_format_br_date_none_returns_dash():
    assert format_br_date(None) == "-"


def test_format_br_date_custom_empty():
    assert format_br_date(None, empty_value="N/A") == "N/A"


# --- format_brl_currency ---

def test_format_brl_currency_simple():
    assert format_brl_currency(Decimal("100.50")) == "R$ 100,50"


def test_format_brl_currency_thousands():
    assert format_brl_currency(Decimal("1234.56")) == "R$ 1.234,56"


def test_format_brl_currency_negative():
    assert format_brl_currency(Decimal("-50.00")) == "R$ -50,00"


def test_format_brl_currency_none_returns_dash():
    assert format_brl_currency(None) == "-"


def test_format_brl_currency_string_input():
    assert format_brl_currency("100.00") == "R$ 100,00"


# --- format_brl_amount ---

def test_format_brl_amount_without_symbol():
    assert format_brl_amount(Decimal("100.50")) == "100,50"


def test_format_brl_amount_with_symbol():
    assert format_brl_amount(Decimal("100.50"), include_symbol=True) == "R$ 100,50"


def test_format_brl_amount_none():
    assert format_brl_amount(None) == "-"


# --- parse_brl_decimal ---

def test_parse_brl_decimal_from_brl_string():
    assert parse_brl_decimal("R$ 1.234,56") == Decimal("1234.56")


def test_parse_brl_decimal_from_plain_decimal():
    assert parse_brl_decimal(Decimal("100.00")) == Decimal("100.00")


def test_parse_brl_decimal_from_integer_string():
    assert parse_brl_decimal("100") == Decimal("100")


def test_parse_brl_decimal_none_returns_default():
    assert parse_brl_decimal(None) is None


def test_parse_brl_decimal_invalid_returns_default():
    assert parse_brl_decimal("nao-e-numero", default=Decimal("0")) == Decimal("0")


def test_parse_brl_decimal_empty_string():
    assert parse_brl_decimal("") is None


# --- parse_br_date ---

def test_parse_br_date_valid():
    assert parse_br_date("15/04/2026") == "2026-04-15"


def test_parse_br_date_none():
    assert parse_br_date(None) is None


def test_parse_br_date_empty():
    assert parse_br_date("") is None


def test_parse_br_date_invalid_format():
    assert parse_br_date("2026-04-15") is None


def test_parse_br_date_strips_whitespace():
    assert parse_br_date("  15/04/2026  ") == "2026-04-15"
