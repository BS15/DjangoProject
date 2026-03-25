"""
Turnpike Resilience Test Suite
===============================

This module *actively attempts to bypass* the ``Processo`` state-machine
guards ("Turnpike / Porteira"), verifying that every rule raises
``ValidationError`` when an illegal move is attempted.

Phase 1  – Explicit bypass attempts
Phase 2  – Property-based fuzzing via Hypothesis
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from processos.models import (
    ComprovanteDePagamento,
    DocumentoProcesso,
    Processo,
    StatusChoicesProcesso,
    TiposDeDocumento,
)
from processos.models.fiscal import DocumentoFiscal


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_processo(status_text):
    """Create (or reuse) a Processo with the given status label."""
    status_obj, _ = StatusChoicesProcesso.objects.get_or_create(
        status_choice=status_text
    )
    return Processo.objects.create(status=status_obj)


def _add_document(processo, tipo_nome):
    """Attach a DocumentoProcesso of *tipo_nome* to *processo*."""
    tipo, _ = TiposDeDocumento.objects.get_or_create(
        tipo_de_documento=tipo_nome
    )
    return DocumentoProcesso.objects.create(
        processo=processo,
        tipo=tipo,
        arquivo='dummy/path.pdf',
        ordem=1,
    )


def _add_nota_fiscal(processo, atestada=True):
    """Attach a minimal DocumentoFiscal to *processo*."""
    return DocumentoFiscal.objects.create(
        processo=processo,
        numero_nota_fiscal='NF-001',
        data_emissao='2024-01-01',
        valor_bruto='1000.00',
        valor_liquido='900.00',
        atestada=atestada,
    )


# ---------------------------------------------------------------------------
# Phase 1 – Explicit bypass attempts
# ---------------------------------------------------------------------------

class TurnpikeBypassTest(TestCase):
    """Actively attempts to bypass the Processo state-machine guards."""

    # ------------------------------------------------------------------ #
    # Test 1 – A EMPENHAR → AGUARDANDO LIQUIDAÇÃO without required doc    #
    # ------------------------------------------------------------------ #

    def test_bypass_empenho_sem_documento(self):
        """
        Attempt: advance 'A EMPENHAR' → 'AGUARDANDO LIQUIDAÇÃO' WITHOUT
        attaching the required 'DOCUMENTOS ORÇAMENTÁRIOS' document.

        Expected: ``ValidationError`` is raised and its message mentions
        "DOCUMENTOS ORÇAMENTÁRIOS".
        """
        processo = _make_processo('A EMPENHAR')

        with self.assertRaises(ValidationError) as ctx:
            processo.avancar_status('AGUARDANDO LIQUIDAÇÃO')

        error_messages = ' '.join(ctx.exception.messages)
        self.assertIn('DOCUMENTOS ORÇAMENTÁRIOS', error_messages)

    # ------------------------------------------------------------------ #
    # Test 2 – AGUARDANDO LIQUIDAÇÃO → A PAGAR without attested nota      #
    # ------------------------------------------------------------------ #

    def test_bypass_pagamento_sem_nota(self):
        """
        Attempt: advance 'AGUARDANDO LIQUIDAÇÃO' → 'A PAGAR - PENDENTE
        AUTORIZAÇÃO' without any attested ``DocumentoFiscal``.

        Expected: ``ValidationError`` is raised.
        """
        processo = _make_processo('AGUARDANDO LIQUIDAÇÃO')

        with self.assertRaises(ValidationError):
            processo.avancar_status('A PAGAR - PENDENTE AUTORIZAÇÃO')

    def test_bypass_pagamento_nota_nao_atestada(self):
        """
        Attempt: same transition but with a DocumentoFiscal that has
        ``atestada=False``.

        Expected: ``ValidationError`` is raised and mentions "atestados".
        """
        processo = _make_processo('AGUARDANDO LIQUIDAÇÃO')
        _add_nota_fiscal(processo, atestada=False)

        with self.assertRaises(ValidationError) as ctx:
            processo.avancar_status('A PAGAR - PENDENTE AUTORIZAÇÃO')

        error_messages = ' '.join(ctx.exception.messages)
        self.assertIn('atestados', error_messages)

    # ------------------------------------------------------------------ #
    # Test 3 – Math mismatch: comprovante ≠ valor_liquido                 #
    # ------------------------------------------------------------------ #

    def test_bypass_matematica_comprovantes(self):
        """
        Attempt: advance 'LANÇADO - AGUARDANDO COMPROVANTE' → 'PAGO - EM
        CONFERÊNCIA' when ``valor_liquido`` is R$ 1 000,00 but a single
        ``ComprovanteDePagamento`` of only R$ 500,00 is attached.

        Expected: ``ValidationError`` whose message contains both "500" and
        "1000" (the mismatched amounts).
        """
        processo = _make_processo('LANÇADO - AGUARDANDO COMPROVANTE')
        processo.valor_liquido = Decimal('1000.00')
        processo.save(update_fields=['valor_liquido'])

        # The first check in Rule 3 requires at least one COMPROVANTE DE
        # PAGAMENTO document – satisfy it so the math check fires.
        _add_document(processo, 'COMPROVANTE DE PAGAMENTO')

        ComprovanteDePagamento.objects.create(
            processo=processo,
            valor_pago=Decimal('500.00'),
        )

        with self.assertRaises(ValidationError) as ctx:
            processo.avancar_status('PAGO - EM CONFERÊNCIA')

        error_messages = ' '.join(ctx.exception.messages)
        self.assertIn('500', error_messages)
        self.assertIn('1000', error_messages)

    # ------------------------------------------------------------------ #
    # Test 4 – Forged / obfuscated status string                          #
    # ------------------------------------------------------------------ #

    def test_forged_status_string(self):
        """
        Attempt: call ``avancar_status`` with a mixed-case, padded variant
        of 'A PAGAR - PENDENTE AUTORIZAÇÃO' (i.e. the attacker hopes the
        normalisation step strips the case but skips the gate check).

        Expected: ``ValidationError`` is still raised because the validator
        normalises the string with ``.upper().strip()`` *before* applying
        the guard rules, so the rule fires correctly.
        """
        processo = _make_processo('AGUARDANDO LIQUIDAÇÃO')
        # No documentos fiscais → the gate MUST block the transition.

        with self.assertRaises(ValidationError):
            processo.avancar_status(' a PaGaR - PENDENTE auTorização   ')


# ---------------------------------------------------------------------------
# Phase 2 – Property-based fuzzing (Hypothesis)
# ---------------------------------------------------------------------------

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase as HypothesisTestCase  # rolls back DB between examples


class TurnpikeFuzzTest(HypothesisTestCase):
    """
    Hypothesis fuzz tests: throws thousands of random inputs at the
    state-machine to ensure it never raises an *unexpected* exception.

    A ``ValidationError`` is always acceptable (the guard blocked the move).
    Any other exception type indicates a bug.
    """

    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    @given(target_status=st.text(min_size=1, max_size=200))
    def test_fuzz_avancar_status_never_crashes_unexpectedly(self, target_status):
        """
        Calling ``avancar_status`` with *any* string must either succeed or
        raise ``ValidationError``; it must NEVER raise any other exception
        type (e.g. ``AttributeError``, ``TypeError``, ``IntegrityError``).
        """
        status_obj, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice='A EMPENHAR'
        )
        processo = Processo.objects.create(status=status_obj)
        try:
            processo.avancar_status(target_status)
        except ValidationError:
            pass  # Expected – the guard correctly blocked the move

    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    @given(
        valor_liquido=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('999999.99'),
            allow_nan=False,
            allow_infinity=False,
            places=2,
        ),
        valor_pago=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('999999.99'),
            allow_nan=False,
            allow_infinity=False,
            places=2,
        ),
    )
    def test_fuzz_math_validation_always_fires_on_mismatch(
        self, valor_liquido, valor_pago
    ):
        """
        For any pair ``(valor_liquido, valor_pago)`` that differs by more
        than R$ 0.01 the math guard must raise ``ValidationError``.
        When both values agree (within tolerance) no math error should fire.
        """
        status_obj, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice='LANÇADO - AGUARDANDO COMPROVANTE'
        )
        processo = Processo.objects.create(
            status=status_obj,
            valor_liquido=valor_liquido,
        )

        tipo, _ = TiposDeDocumento.objects.get_or_create(
            tipo_de_documento='COMPROVANTE DE PAGAMENTO'
        )
        DocumentoProcesso.objects.create(
            processo=processo,
            tipo=tipo,
            arquivo='dummy/path.pdf',
            ordem=1,
        )
        ComprovanteDePagamento.objects.create(
            processo=processo,
            valor_pago=valor_pago,
        )

        diferenca = abs(float(valor_pago) - float(valor_liquido))

        if diferenca > 0.01:
            with self.assertRaises(ValidationError) as ctx:
                processo.avancar_status('PAGO - EM CONFERÊNCIA')
            error_messages = ' '.join(ctx.exception.messages)
            # The math error message must mention the word "diferente"
            self.assertIn('diferente', error_messages.lower())
        else:
            # Values match – the math guard must NOT fire.
            # (Other guards may fire for unrelated reasons; that is acceptable.)
            try:
                processo.avancar_status('PAGO - EM CONFERÊNCIA')
            except ValidationError as exc:
                # Only fail if the math guard specifically fired
                math_error = any(
                    'diferente' in msg.lower()
                    for msg in exc.messages
                )
                self.assertFalse(
                    math_error,
                    f'Math guard fired unexpectedly for matching values '
                    f'({valor_pago} vs {valor_liquido}): {exc.messages}',
                )
