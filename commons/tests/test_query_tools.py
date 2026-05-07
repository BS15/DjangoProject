"""Testes unitários para commons/shared/query_tools.py."""

from unittest.mock import MagicMock

import pytest

from commons.shared.query_tools import (
    aplicar_filtro_por_opcao,
    obter_campo_ordenacao,
    resolver_parametros_ordenacao,
)


def _fake_request(params: dict):
    req = MagicMock()
    req.GET = params
    return req


CAMPOS = {
    "nome": "credor__nome",
    "valor": "valor_bruto",
    "id": "id",
}


# --- resolver_parametros_ordenacao ---

def test_resolver_campo_e_direcao_validos():
    req = _fake_request({"ordem": "nome", "direcao": "asc"})
    ordem, direcao, order_field = resolver_parametros_ordenacao(req, CAMPOS)
    assert ordem == "nome"
    assert direcao == "asc"
    assert order_field == "credor__nome"


def test_resolver_direcao_desc_adiciona_prefixo():
    req = _fake_request({"ordem": "valor", "direcao": "desc"})
    _, _, order_field = resolver_parametros_ordenacao(req, CAMPOS)
    assert order_field == "-valor_bruto"


def test_resolver_campo_invalido_usa_default():
    req = _fake_request({"ordem": "inexistente", "direcao": "asc"})
    ordem, _, _ = resolver_parametros_ordenacao(req, CAMPOS, default_ordem="id")
    assert ordem == "id"


def test_resolver_direcao_invalida_usa_default():
    req = _fake_request({"ordem": "nome", "direcao": "invalido"})
    _, direcao, _ = resolver_parametros_ordenacao(req, CAMPOS, default_direcao="asc")
    assert direcao == "asc"


def test_resolver_sem_parametros_usa_defaults():
    req = _fake_request({})
    ordem, direcao, order_field = resolver_parametros_ordenacao(req, CAMPOS)
    assert ordem == "id"
    assert direcao == "desc"
    assert order_field == "-id"


# --- obter_campo_ordenacao ---

def test_obter_campo_apenas_retorna_order_field():
    req = _fake_request({"ordem": "nome", "direcao": "asc"})
    order_field = obter_campo_ordenacao(req, CAMPOS)
    assert order_field == "credor__nome"


def test_obter_campo_sem_params_retorna_default():
    req = _fake_request({})
    order_field = obter_campo_ordenacao(req, CAMPOS)
    assert order_field == "-id"


# --- aplicar_filtro_por_opcao ---

def test_filtro_por_kwargs():
    qs = MagicMock()
    qs.filter.return_value = qs
    mapa = {"pago": {"status__opcao_status": "PAGO"}}
    resultado = aplicar_filtro_por_opcao(qs, "pago", mapa)
    qs.filter.assert_called_once_with(status__opcao_status="PAGO")


def test_filtro_por_callable():
    qs = MagicMock()
    mapa = {"grandes": lambda q: q.filter(valor_bruto__gte=1000)}
    resultado = aplicar_filtro_por_opcao(qs, "grandes", mapa)
    qs.filter.assert_called_once_with(valor_bruto__gte=1000)


def test_filtro_opcao_inexistente_retorna_qs_original():
    qs = MagicMock()
    resultado = aplicar_filtro_por_opcao(qs, "inexistente", {})
    assert resultado is qs
    qs.filter.assert_not_called()
