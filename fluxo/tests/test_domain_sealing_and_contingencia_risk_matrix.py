from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from fluxo.domain_models import Contingencia, ProcessoStatus
from fluxo.validators import verificar_turnpike
from fluxo.views.helpers.contingencias import (
    aplicar_aprovacao_contingencia,
    normalizar_dados_propostos_contingencia,
)
from fluxo.views.pre_payment.cadastro.actions import _status_bloqueia_gestao_fiscal


@pytest.mark.django_db
def test_bloqueio_pos_pagamento_ativa_guard_de_gestao_fiscal(processo_factory):
    processo = processo_factory(status=ProcessoStatus.PAGO_EM_CONFERENCIA)
    assert _status_bloqueia_gestao_fiscal(processo) is True


@pytest.mark.django_db
def test_bypass_direto_por_payload_deveria_ser_bloqueado_no_dominio(processo_factory):
    processo = processo_factory(status=ProcessoStatus.PAGO_EM_CONFERENCIA)
    payload_espurio = {
        "valor_liquido": Decimal("1.00"),
        "detalhamento": "MUTACAO_DIRETA_ESPURIA",
    }

    assert _status_bloqueia_gestao_fiscal(processo) is True

    with pytest.raises(ValidationError):
        for campo, valor in payload_espurio.items():
            setattr(processo, campo, valor)
        processo.save(update_fields=list(payload_espurio.keys()))


@pytest.mark.django_db
def test_bloqueio_pos_pagamento_libera_fluxo_quando_em_contingencia(processo_factory):
    processo = processo_factory(status=ProcessoStatus.PAGO_EM_CONFERENCIA)
    processo.em_contingencia = True
    processo.save(update_fields=["em_contingencia"])
    assert _status_bloqueia_gestao_fiscal(processo) is False


@pytest.mark.django_db
def test_contingencia_aprovada_requer_coerencia_com_comprovantes(
    processo_factory,
    add_comprovante,
    user_factory,
):
    processo = processo_factory(status=ProcessoStatus.PAGO_EM_CONFERENCIA)
    processo.valor_liquido = Decimal("100.00")
    processo.save(update_fields=["valor_liquido"])
    add_comprovante(processo, valor_pago=Decimal("100.00"))

    contingencia = Contingencia.objects.create(
        processo=processo,
        solicitante=user_factory("solicitante"),
        justificativa="Ajuste regular",
        dados_propostos={"valor_liquido": "120,00"},
    )

    ok, erro = aplicar_aprovacao_contingencia(contingencia)
    assert ok is False
    assert erro is not None


@pytest.mark.django_db
def test_contingencia_agressiva_aborta_na_raiz_quando_novo_valor_nao_fecha_com_comprovantes(
    processo_factory,
    add_comprovante,
    user_factory,
):
    processo = processo_factory(status=ProcessoStatus.LANCADO_AGUARDANDO_COMPROVANTE)
    processo.valor_liquido = Decimal("100.00")
    processo.save(update_fields=["valor_liquido"])
    add_comprovante(processo, valor_pago=Decimal("100.00"))

    contingencia = Contingencia.objects.create(
        processo=processo,
        solicitante=user_factory("solicitante2"),
        justificativa="Ajuste para baixo",
        dados_propostos={"valor_liquido": "90,00"},
    )

    ok, erro = aplicar_aprovacao_contingencia(contingencia)
    assert ok is False
    assert erro is not None


@pytest.mark.django_db
def test_contingencia_descarta_campos_fora_da_whitelist():
    payload = {
        "valor_liquido": "100,00",
        "campo_malicioso": "DROP TABLE",
        "status": "ARQUIVADO",
    }
    normalizado = normalizar_dados_propostos_contingencia(payload)
    assert "valor_liquido" in normalizado
    assert "campo_malicioso" not in normalizado
    assert "status" not in normalizado
