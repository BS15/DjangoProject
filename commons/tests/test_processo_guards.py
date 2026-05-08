"""Testes de integração para commons/shared/processo_guards.py."""

import pytest

from commons.shared.processo_guards import is_processo_selado
from pagamentos.domain_models import ProcessoStatus


# --- is_processo_selado ---

@pytest.mark.django_db
def test_processo_none_nao_selado():
    assert is_processo_selado(None) is False


@pytest.mark.django_db
def test_processo_em_contingencia_nao_selado(processo_factory):
    processo = processo_factory(status=ProcessoStatus.PAGO_EM_CONFERENCIA)
    processo.em_contingencia = True
    processo.save(update_fields=["em_contingencia"])
    assert is_processo_selado(processo) is False


@pytest.mark.django_db
def test_processo_pre_pagamento_nao_selado(processo_factory):
    processo = processo_factory(status=ProcessoStatus.A_EMPENHAR)
    assert is_processo_selado(processo) is False


@pytest.mark.django_db
def test_processo_aguardando_liquidacao_nao_selado(processo_factory):
    processo = processo_factory(status=ProcessoStatus.AGUARDANDO_LIQUIDACAO)
    assert is_processo_selado(processo) is False


@pytest.mark.django_db
def test_processo_pago_em_conferencia_selado(processo_factory):
    processo = processo_factory(status=ProcessoStatus.PAGO_EM_CONFERENCIA)
    assert is_processo_selado(processo) is True


@pytest.mark.django_db
def test_processo_pago_a_contabilizar_selado(processo_factory):
    processo = processo_factory(status=ProcessoStatus.PAGO_A_CONTABILIZAR)
    assert is_processo_selado(processo) is True


@pytest.mark.django_db
def test_processo_contabilizado_selado(processo_factory):
    processo = processo_factory(status=ProcessoStatus.CONTABILIZADO_CONSELHO)
    assert is_processo_selado(processo) is True


@pytest.mark.django_db
def test_processo_aprovado_pendente_arquivamento_selado(processo_factory):
    processo = processo_factory(status=ProcessoStatus.APROVADO_PENDENTE_ARQUIVAMENTO)
    assert is_processo_selado(processo) is True


@pytest.mark.django_db
def test_processo_arquivado_selado(processo_factory):
    processo = processo_factory(status=ProcessoStatus.ARQUIVADO)
    assert is_processo_selado(processo) is True


@pytest.mark.django_db
def test_processo_sem_status_nao_selado():
    """Um processo mock sem status não deve ser considerado selado."""
    from unittest.mock import MagicMock
    processo_mock = MagicMock()
    processo_mock.em_contingencia = False
    processo_mock.status = None  # MagicMock com status=None
    # is_processo_selado deve retornar False quando status é None/falsy
    from commons.shared.processo_guards import is_processo_selado
    assert is_processo_selado(processo_mock) is False
