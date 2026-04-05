"""Tests for deterministic matching primitives shared by SISCAC/comprovantes flows."""

from datetime import datetime
from decimal import Decimal

from django.test import SimpleTestCase

from processos.utils import (
    decimals_equal_money,
    format_brl_amount,
    format_br_date,
    format_brl_currency,
    names_bidirectional_match,
    normalize_account,
    normalize_choice,
    normalize_document,
    normalize_text,
    parse_brl_decimal,
    normalize_name_for_match,
)


class MatchingPrimitivesTest(SimpleTestCase):
    """Validates normalization and comparison helpers used across matching pipelines."""

    def test_normalize_document_removes_mask(self):
        self.assertEqual(normalize_document("82.894.098/0001-32"), "82894098000132")
        self.assertEqual(normalize_document("123.456.789-00"), "12345678900")

    def test_normalize_account_strips_noise(self):
        self.assertEqual(normalize_account("3582-3", "7.429-2"), ("3582-3", "7429-2"))
        self.assertEqual(normalize_account(" 1234 ", " 0001.9x "), ("1234", "00019X"))

    def test_normalize_name_for_match_removes_accents_and_spaces(self):
        self.assertEqual(normalize_name_for_match("  José   da  Silva  "), "JOSE DA SILVA")
        self.assertEqual(normalize_name_for_match("MÁRCIA"), "MARCIA")

    def test_normalize_text_can_preserve_internal_spacing(self):
        self.assertEqual(normalize_text(" João   da Silva "), "JOAO DA SILVA")
        self.assertEqual(normalize_text(" João   da Silva ", collapse_spaces=False), "JOAO   DA SILVA")

    def test_names_bidirectional_match_accepts_contains(self):
        self.assertTrue(names_bidirectional_match("JOAO SILVA", "Joao"))
        self.assertTrue(names_bidirectional_match("Conselho Regional", "conselho regional de administracao"))
        self.assertFalse(names_bidirectional_match("ALFA LTDA", "BETA LTDA"))

    def test_decimals_equal_money_compares_cent_values(self):
        self.assertTrue(decimals_equal_money(Decimal("100.0"), Decimal("100.00")))
        self.assertTrue(decimals_equal_money(Decimal("100.005"), Decimal("100.01")))
        self.assertFalse(decimals_equal_money(Decimal("100.00"), Decimal("100.02")))
        self.assertFalse(decimals_equal_money(None, Decimal("1.00")))

    def test_normalize_choice_rejects_invalid_values(self):
        self.assertEqual(normalize_choice("asc", {"asc", "desc"}, default="desc"), "asc")
        self.assertEqual(normalize_choice("sideways", {"asc", "desc"}, default="desc"), "desc")

    def test_format_br_date_uses_brazilian_pattern(self):
        self.assertEqual(format_br_date(datetime(2026, 4, 4).date()), "04/04/2026")
        self.assertEqual(format_br_date(None), "-")

    def test_format_brl_currency_uses_local_separators(self):
        self.assertEqual(format_brl_currency(Decimal("1234.56")), "R$ 1.234,56")
        self.assertEqual(format_brl_currency(Decimal("-10")), "R$ -10,00")
        self.assertEqual(format_brl_currency(None), "-")

    def test_format_brl_amount_can_omit_currency_symbol(self):
        self.assertEqual(format_brl_amount(Decimal("1234.56")), "1.234,56")
        self.assertEqual(format_brl_amount(Decimal("1234.56"), include_symbol=True), "R$ 1.234,56")
        self.assertEqual(format_brl_amount(None, empty_value="0,00"), "0,00")

    def test_parse_brl_decimal_accepts_localized_strings(self):
        self.assertEqual(parse_brl_decimal("1.234,56"), Decimal("1234.56"))
        self.assertEqual(parse_brl_decimal("R$ 99,90"), Decimal("99.90"))
        self.assertEqual(parse_brl_decimal("10.50"), Decimal("10.50"))
        self.assertIsNone(parse_brl_decimal("invalido"))
