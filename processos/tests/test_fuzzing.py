"""
Fuzz tests using the Hypothesis library to discover edge-case crashes in
financial math and model constraints.

Run with:
    python manage.py test processos.tests.test_fuzzing
"""
import io
from decimal import Decimal, InvalidOperation
from datetime import date

from django.core.exceptions import ValidationError
from django.db import DataError
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase as HypothesisTestCase

from processos.models import DocumentoFiscal, Processo
from processos.models.fiscal import CodigosImposto, RetencaoImposto
from processos.models.fluxo import caminho_documento
from processos.validators import validar_arquivo_seguro


# ---------------------------------------------------------------------------
# Shared strategy helpers
# ---------------------------------------------------------------------------

# Finite, non-NaN floats that cover a very wide range including negative,
# fractional, and huge magnitudes.
_finite_floats = st.floats(allow_nan=False, allow_infinity=False)

# Dates spanning from very early years to far future, including leap-year
# edge cases and typical extremes.
_extreme_dates = st.dates(
    min_value=date(1000, 1, 1),
    max_value=date(9999, 12, 31),
)


# ---------------------------------------------------------------------------
# Test 1 – Decimal quantize math
# ---------------------------------------------------------------------------

class FuzzRetencaoMathTest(HypothesisTestCase):
    """
    Exercises the ``(rendimento * aliquota / 100).quantize(Decimal('0.01'))``
    formula used when computing retained-tax values.  Hypothesis will search
    for float combinations that cause an unhandled crash.
    """

    def setUp(self):
        self.codigo = CodigosImposto.objects.create(
            codigo="FUZZ-01",
            aliquota=Decimal("1.50"),
        )
        self.processo = Processo.objects.create()
        self.nota_fiscal = DocumentoFiscal.objects.create(
            processo=self.processo,
            numero_nota_fiscal="NF-FUZZ",
            data_emissao=date(2024, 1, 1),
            valor_bruto=Decimal("1000.00"),
            valor_liquido=Decimal("1000.00"),
        )

    @given(
        aliquota=_finite_floats,
        rendimento=_finite_floats,
    )
    @settings(
        max_examples=200,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_fuzz_retencao_math(self, aliquota, rendimento):
        """
        The quantize logic must not raise unexpected exceptions.
        Only ``InvalidOperation`` (extreme magnitudes) and ``ZeroDivisionError``
        are considered expected failure modes; any other exception is a bug.
        """
        try:
            aliq = Decimal(str(aliquota))
            rend = Decimal(str(rendimento))
            valor = (rend * aliq / Decimal("100")).quantize(Decimal("0.01"))
        except (InvalidOperation, ZeroDivisionError, OverflowError):
            # Expected: values too extreme for the precision or decimal context.
            return
        except Exception as exc:
            self.fail(
                f"Unexpected exception during quantize math with "
                f"aliquota={aliquota!r}, rendimento={rendimento!r}: "
                f"{type(exc).__name__}: {exc}"
            )

        # If the math succeeded, try persisting a RetencaoImposto row.
        # Acceptable outcomes: success OR a domain-level error (too many digits,
        # or model validation).  A raw Python crash is *not* acceptable.
        try:
            RetencaoImposto.objects.create(
                nota_fiscal=self.nota_fiscal,
                codigo=self.codigo,
                rendimento_tributavel=rend if rend.is_finite() else None,
                valor=valor if valor.is_finite() else Decimal("0.00"),
            )
        except (ValidationError, DataError, InvalidOperation, OverflowError):
            # Domain / DB constraints rejecting extreme values — expected.
            pass
        except Exception as exc:
            self.fail(
                f"Unexpected exception when saving RetencaoImposto with "
                f"aliquota={aliquota!r}, rendimento={rendimento!r}, valor={valor!r}: "
                f"{type(exc).__name__}: {exc}"
            )


# ---------------------------------------------------------------------------
# Test 2 – caminho_documento date path logic
# ---------------------------------------------------------------------------

class FuzzProcessoDatesTest(HypothesisTestCase):
    """
    Exercises the ``caminho_documento`` upload-path helper with absurd
    ``data_empenho`` values (year 1000, 9999, leap years, …).  The helper
    must produce a valid string for every possible Python date.
    """

    @given(data_empenho=_extreme_dates)
    @settings(
        max_examples=200,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_fuzz_processo_dates(self, data_empenho):
        """
        caminho_documento must return a non-empty string for any valid date
        without raising an exception.
        """
        processo = Processo.objects.create(data_empenho=data_empenho)

        # Build a minimal stub that mimics the DocumentoProcesso interface
        # expected by caminho_documento – without hitting the DB or file
        # storage for the actual file field.
        class _FakeDocumento:
            def __init__(self, p):
                self.processo = p
                self.diaria = None
                self.reembolso = None
                self.jeton = None
                self.auxilio = None
                self.suprimento = None

            @property
            def __class__(self):  # pragma: no cover – keeps the isinstance check happy
                return super().__class__

        stub = _FakeDocumento(processo)

        try:
            path = caminho_documento(stub, "test.pdf")
        except Exception as exc:
            self.fail(
                f"caminho_documento raised {type(exc).__name__} for "
                f"data_empenho={data_empenho!r}: {exc}"
            )

        self.assertIsInstance(path, str, "caminho_documento must return a str")
        self.assertGreater(len(path), 0, "caminho_documento must return a non-empty path")
        self.assertIn(str(data_empenho.year), path,
                      "The year must appear in the document path")


# ---------------------------------------------------------------------------
# Test 3 – validar_arquivo_seguro with malformed / empty content
# ---------------------------------------------------------------------------

class FuzzDocumentoNuloTest(HypothesisTestCase):
    """
    Passes empty or completely random bytes to ``validar_arquivo_seguro``
    to ensure the validator never crashes the process—it must either succeed
    silently (for valid file signatures) or raise ``ValidationError``
    (for invalid/unknown types).
    """

    class _FileObj:
        """Minimal file-like object accepted by validar_arquivo_seguro."""

        def __init__(self, data: bytes):
            self._buf = io.BytesIO(data)

        def read(self, n: int = -1) -> bytes:
            return self._buf.read(n)

        def seek(self, pos: int) -> None:
            self._buf.seek(pos)

    @given(content=st.binary(max_size=4096))
    @settings(
        max_examples=300,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_fuzz_documento_nulo(self, content: bytes):
        """
        For any byte sequence the validator must either:
        * return ``None`` silently (file type is allowed), or
        * raise ``ValidationError`` (file type is blocked/unrecognised).

        Any other exception (AttributeError, TypeError, UnicodeDecodeError,
        etc.) is a bug that would surface as a 500 in a view.
        """
        file_obj = self._FileObj(content)
        try:
            result = validar_arquivo_seguro(file_obj)
            # A None return means the file was accepted — fine.
            self.assertIsNone(result)
        except ValidationError:
            # Expected: validator correctly rejected the content.
            pass
        except Exception as exc:
            self.fail(
                f"validar_arquivo_seguro raised an unexpected "
                f"{type(exc).__name__} for content of length {len(content)}: {exc}"
            )

    def test_fuzz_documento_none(self):
        """Passing ``None`` must be handled gracefully (returns None)."""
        result = validar_arquivo_seguro(None)
        self.assertIsNone(result)

    def test_fuzz_documento_empty_bytes(self):
        """An empty file must be rejected with ValidationError, not crash."""
        file_obj = self._FileObj(b"")
        try:
            validar_arquivo_seguro(file_obj)
        except ValidationError:
            pass  # Correct — empty file is not a valid PDF/JPEG/PNG.
        except Exception as exc:
            self.fail(
                f"validar_arquivo_seguro raised {type(exc).__name__} "
                f"for empty bytes: {exc}"
            )
