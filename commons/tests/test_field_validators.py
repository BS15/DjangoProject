"""Testes unitários para commons/shared/field_validators.py."""

import pytest
from django.core.exceptions import ValidationError

from commons.shared.field_validators import validar_cpf_cnpj


# --- CPF válido ---

def test_valida_cpf_com_formatacao():
    validar_cpf_cnpj("123.456.789-01")


def test_valida_cpf_apenas_digitos():
    validar_cpf_cnpj("12345678901")


def test_valida_cnpj_com_formatacao():
    validar_cpf_cnpj("12.345.678/0001-99")


def test_valida_cnpj_apenas_digitos():
    validar_cpf_cnpj("12345678000199")


# --- None / vazio ignora validação ---

def test_none_nao_levanta_excecao():
    validar_cpf_cnpj(None)


def test_vazio_nao_levanta_excecao():
    validar_cpf_cnpj("")


# --- CPF inválido: tamanho errado ---

def test_cpf_com_dez_digitos_invalido():
    with pytest.raises(ValidationError, match="11 dígitos"):
        validar_cpf_cnpj("1234567890")


def test_cpf_com_doze_digitos_invalido():
    with pytest.raises(ValidationError):
        validar_cpf_cnpj("123456789012")


# --- CPF inválido: dígitos repetidos ---

def test_cpf_todos_zeros_invalido():
    with pytest.raises(ValidationError, match="repetidos"):
        validar_cpf_cnpj("00000000000")


def test_cpf_todos_uns_invalido():
    with pytest.raises(ValidationError, match="repetidos"):
        validar_cpf_cnpj("11111111111")


# --- CNPJ inválido: dígitos repetidos ---

def test_cnpj_todos_zeros_invalido():
    with pytest.raises(ValidationError, match="repetidos"):
        validar_cpf_cnpj("00000000000000")


# --- tamanho intermediário ---

def test_numero_com_13_digitos_invalido():
    with pytest.raises(ValidationError):
        validar_cpf_cnpj("1234567890123")
