"""Testes unitários para commons/shared/file_validators.py."""

import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile


def _make_file(content: bytes, name: str = "test.pdf") -> InMemoryUploadedFile:
    buf = io.BytesIO(content)
    buf.name = name
    return InMemoryUploadedFile(buf, "arquivo", name, None, len(content), None)


# Cabeçalhos mínimos reais por tipo MIME
_PDF_MAGIC = b"%PDF-1.4" + b"\x00" * 500
_JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 500
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 500
_ZIP_MAGIC = b"PK\x03\x04" + b"\x00" * 500


@pytest.fixture
def validar():
    from commons.shared.file_validators import validar_arquivo_seguro
    return validar_arquivo_seguro


def test_pdf_aceito(validar):
    f = _make_file(_PDF_MAGIC, "doc.pdf")
    validar(f)  # não deve levantar


def test_jpeg_aceito(validar):
    f = _make_file(_JPEG_MAGIC, "foto.jpg")
    validar(f)  # não deve levantar


def test_png_aceito(validar):
    # Minimal valid 1x1 PNG
    import base64
    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    png_data = base64.b64decode(png_b64) + b"\x00" * 500
    f = _make_file(png_data, "imagem.png")
    validar(f)  # não deve levantar


def test_zip_rejeitado(validar):
    f = _make_file(_ZIP_MAGIC, "arquivo.zip")
    with pytest.raises(ValidationError, match="não permitido"):
        validar(f)


def test_arquivo_none_nao_levanta(validar):
    validar(None)


def test_arquivo_leitura_falha_levanta(validar, monkeypatch):
    import magic

    monkeypatch.setattr(magic, "from_buffer", lambda *_a, **_kw: (_ for _ in ()).throw(magic.MagicException("falhou")))
    f = _make_file(_PDF_MAGIC)
    with pytest.raises(ValidationError, match="verificar"):
        validar(f)
