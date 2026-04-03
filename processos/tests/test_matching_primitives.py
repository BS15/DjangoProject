"""Tests for deterministic matching primitives shared by SISCAC/comprovantes flows."""

from decimal import Decimal

from django.test import SimpleTestCase

from processos.utils import (
    decimals_equal_money,
    names_bidirectional_match,
    normalize_account,
    normalize_document,
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

    def test_names_bidirectional_match_accepts_contains(self):
        self.assertTrue(names_bidirectional_match("JOAO SILVA", "Joao"))
        self.assertTrue(names_bidirectional_match("Conselho Regional", "conselho regional de administracao"))
        self.assertFalse(names_bidirectional_match("ALFA LTDA", "BETA LTDA"))

    def test_decimals_equal_money_compares_cent_values(self):
        self.assertTrue(decimals_equal_money(Decimal("100.0"), Decimal("100.00")))
        self.assertTrue(decimals_equal_money(Decimal("100.005"), Decimal("100.01")))
        self.assertFalse(decimals_equal_money(Decimal("100.00"), Decimal("100.02")))
        self.assertFalse(decimals_equal_money(None, Decimal("1.00")))
