"""Testes unitários para commons/shared/csv_import_utils.py."""

import io

import pytest

from commons.shared.csv_import_utils import build_csv_dict_reader, decode_csv_file


# --- decode_csv_file ---

def _file(content: bytes):
    buf = io.BytesIO(content)
    buf.read = buf.read
    return buf


def test_decode_utf8():
    f = io.BytesIO(b"coluna1,coluna2\nvalor1,valor2")
    decoded, erro = decode_csv_file(f, ("utf-8",), "erro")
    assert erro is None
    assert "coluna1" in decoded


def test_decode_latin1_fallback():
    texto = "Nome,Descrição\nJoão,Ação\n"
    f = io.BytesIO(texto.encode("latin-1"))
    decoded, erro = decode_csv_file(f, ("utf-8", "latin-1"), "erro")
    assert erro is None
    assert "João" in decoded


def test_decode_falha_todos_encodings():
    # Bytes que não são válidos em nenhum encoding comum
    f = io.BytesIO(b"\xff\xfe" * 100)
    decoded, erro = decode_csv_file(f, ("ascii",), "Erro de decodificação")
    assert decoded is None
    assert erro == "Erro de decodificação"


def test_decode_str_passthrough():
    """Se já for str, retorna diretamente."""
    class FakeFile:
        def read(self):
            return "coluna1,coluna2\n"
    decoded, erro = decode_csv_file(FakeFile(), ("utf-8",), "erro")
    assert decoded == "coluna1,coluna2\n"
    assert erro is None


# --- build_csv_dict_reader ---

def _csv_bytes(content: str) -> io.BytesIO:
    return io.BytesIO(content.encode("utf-8"))


def test_reader_sem_colunas_obrigatorias():
    f = _csv_bytes("a,b\n1,2\n")
    reader, erro = build_csv_dict_reader(
        f,
        encodings=("utf-8",),
        encoding_error_message="erro",
    )
    assert erro is None
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["a"] == "1"


def test_reader_com_colunas_presentes():
    f = _csv_bytes("nome,cpf\nJoão,12345678901\n")
    reader, erro = build_csv_dict_reader(
        f,
        encodings=("utf-8",),
        encoding_error_message="erro",
        required_columns=("nome", "cpf"),
    )
    assert erro is None
    assert reader is not None


def test_reader_com_coluna_ausente():
    f = _csv_bytes("nome\nJoão\n")
    reader, erro = build_csv_dict_reader(
        f,
        encodings=("utf-8",),
        encoding_error_message="erro",
        required_columns=("nome", "cpf"),
    )
    assert reader is None
    assert "cpf" in erro


def test_reader_encoding_invalido():
    f = io.BytesIO(b"\xff\xfe" * 100)
    reader, erro = build_csv_dict_reader(
        f,
        encodings=("ascii",),
        encoding_error_message="Encoding inválido",
    )
    assert reader is None
    assert erro == "Encoding inválido"


def test_reader_prefixo_mensagem_coluna():
    f = _csv_bytes("nome\nJoão\n")
    _, erro = build_csv_dict_reader(
        f,
        encodings=("utf-8",),
        encoding_error_message="erro",
        required_columns=("email",),
        missing_columns_message_prefix="Colunas faltando:",
    )
    assert erro.startswith("Colunas faltando:")
    assert "email" in erro
