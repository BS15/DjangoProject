"""Testes para verbas_indenizatorias/validators.py (validar_vinculo_inicial_em_processo_selado)."""

import pytest
from django.core.exceptions import ValidationError

from apps.pagamentos.domain_models import ProcessoStatus
from verbas_indenizatorias.validators import validar_vinculo_inicial_em_processo_selado


@pytest.mark.django_db
def test_processo_none_nao_bloqueia():
    """Processo None não deve bloquear o vínculo inicial."""
    validar_vinculo_inicial_em_processo_selado(None, "diária")


@pytest.mark.django_db
def test_processo_pre_pagamento_nao_bloqueia(processo_factory):
    processo = processo_factory(status=ProcessoStatus.AGUARDANDO_LIQUIDACAO)
    validar_vinculo_inicial_em_processo_selado(processo, "diária")


@pytest.mark.django_db
def test_processo_pago_bloqueia_vinculo(processo_factory):
    processo = processo_factory(status=ProcessoStatus.PAGO_EM_CONFERENCIA)
    with pytest.raises(ValidationError, match="pós-pagamento"):
        validar_vinculo_inicial_em_processo_selado(processo, "diária")


@pytest.mark.django_db
def test_processo_pago_em_contingencia_nao_bloqueia(processo_factory):
    processo = processo_factory(status=ProcessoStatus.PAGO_EM_CONFERENCIA)
    processo.em_contingencia = True
    processo.save(update_fields=["em_contingencia"])
    validar_vinculo_inicial_em_processo_selado(processo, "diária")


@pytest.mark.django_db
def test_label_aparece_na_mensagem_de_erro(processo_factory):
    processo = processo_factory(status=ProcessoStatus.PAGO_EM_CONFERENCIA)
    with pytest.raises(ValidationError) as exc_info:
        validar_vinculo_inicial_em_processo_selado(processo, "reembolso")
    assert "reembolso" in str(exc_info.value)
