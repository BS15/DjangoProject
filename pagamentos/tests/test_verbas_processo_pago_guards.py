from datetime import date
from decimal import Decimal
import uuid

import pytest
from django.core.exceptions import ValidationError

from credores.models import Credor
from pagamentos.domain_models import ProcessoStatus, StatusChoicesProcesso
from verbas_indenizatorias.models import AuxilioRepresentacao, Jeton, ReembolsoCombustivel


def _credor_pf():
    return Credor.objects.create(
        nome=f"Credor {uuid.uuid4().hex[:6]}",
        cpf_cnpj=f"{uuid.uuid4().int % 10**11:011d}",
        tipo="PF",
    )


def _novo_reembolso(processo, beneficiario):
    return ReembolsoCombustivel(
        processo=processo,
        beneficiario=beneficiario,
        numero_sequencial=f"R-{uuid.uuid4().hex[:6]}",
        data_saida=date(2026, 4, 1),
        data_retorno=date(2026, 4, 2),
        cidade_origem="Florianopolis",
        cidade_destino="Sao Jose",
        distancia_km=Decimal("10.00"),
        preco_combustivel=Decimal("6.00"),
        valor_total=Decimal("60.00"),
    )


def _novo_jeton(processo, beneficiario):
    return Jeton(
        processo=processo,
        beneficiario=beneficiario,
        numero_sequencial=f"J-{uuid.uuid4().hex[:6]}",
        reuniao="2026/1",
        data_evento=date(2026, 4, 1),
        local_evento="Sede",
        valor_total=Decimal("500.00"),
    )


def _novo_auxilio(processo, beneficiario):
    return AuxilioRepresentacao(
        processo=processo,
        beneficiario=beneficiario,
        numero_sequencial=f"A-{uuid.uuid4().hex[:6]}",
        objetivo="Representacao institucional",
        data_evento=date(2026, 4, 1),
        local_evento="Plenario",
        valor_total=Decimal("400.00"),
    )


def _marcar_processo_como_pago(processo):
    status_pago, _ = StatusChoicesProcesso.objects.get_or_create(
        status_choice__iexact=ProcessoStatus.PAGO_EM_CONFERENCIA,
        defaults={"status_choice": ProcessoStatus.PAGO_EM_CONFERENCIA},
    )
    processo.status = status_pago
    processo.save(update_fields=["status"])


@pytest.mark.django_db
@pytest.mark.parametrize(
    "builder",
    [_novo_reembolso, _novo_jeton, _novo_auxilio],
)
def test_bloqueia_cadastro_de_verba_em_processo_pago(processo_factory, builder):
    processo_pago = processo_factory(status=ProcessoStatus.PAGO_EM_CONFERENCIA)
    beneficiario = _credor_pf()
    verba = builder(processo_pago, beneficiario)

    with pytest.raises(ValidationError):
        verba.save()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "builder",
    [_novo_reembolso, _novo_jeton, _novo_auxilio],
)
def test_bloqueia_desvincular_verba_apos_processo_pago(processo_factory, builder):
    processo = processo_factory(status=ProcessoStatus.A_PAGAR_PENDENTE_AUTORIZACAO)
    beneficiario = _credor_pf()
    verba = builder(processo, beneficiario)
    verba.save()

    _marcar_processo_como_pago(processo)

    verba.processo = None
    with pytest.raises(ValidationError):
        verba.save(update_fields=["processo"])


@pytest.mark.django_db
@pytest.mark.parametrize(
    "builder",
    [_novo_reembolso, _novo_jeton, _novo_auxilio],
)
def test_bloqueia_exclusao_de_verba_apos_processo_pago(processo_factory, builder):
    processo = processo_factory(status=ProcessoStatus.A_PAGAR_PENDENTE_AUTORIZACAO)
    beneficiario = _credor_pf()
    verba = builder(processo, beneficiario)
    verba.save()

    _marcar_processo_como_pago(processo)

    with pytest.raises(ValidationError):
        verba.delete()
