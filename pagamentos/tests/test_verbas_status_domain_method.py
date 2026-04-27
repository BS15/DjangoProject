from datetime import date
from decimal import Decimal
import uuid

import pytest
from django.core.exceptions import ValidationError

from credores.models import Credor
from verbas_indenizatorias.models import (
    AuxilioRepresentacao,
    Diaria,
    Jeton,
    ReembolsoCombustivel,
    StatusChoicesVerbasIndenizatorias,
)


def _credor_pf():
    return Credor.objects.create(
        nome=f"Credor {uuid.uuid4().hex[:6]}",
        cpf_cnpj=f"{uuid.uuid4().int % 10**11:011d}",
        tipo="PF",
    )


def _novo_reembolso(processo, beneficiario):
    return ReembolsoCombustivel.objects.create(
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
    return Jeton.objects.create(
        processo=processo,
        beneficiario=beneficiario,
        numero_sequencial=f"J-{uuid.uuid4().hex[:6]}",
        reuniao="2026/1",
        data_evento=date(2026, 4, 1),
        local_evento="Sede",
        valor_total=Decimal("500.00"),
    )


def _novo_auxilio(processo, beneficiario):
    return AuxilioRepresentacao.objects.create(
        processo=processo,
        beneficiario=beneficiario,
        numero_sequencial=f"A-{uuid.uuid4().hex[:6]}",
        objetivo="Representacao institucional",
        data_evento=date(2026, 4, 1),
        local_evento="Plenario",
        valor_total=Decimal("400.00"),
    )


def _nova_diaria(processo, beneficiario):
    return Diaria.objects.create(
        processo=processo,
        beneficiario=beneficiario,
        tipo_solicitacao="INICIAL",
        data_saida=date(2026, 4, 1),
        data_retorno=date(2026, 4, 2),
        cidade_origem="Florianopolis",
        cidade_destino="Brasilia",
        objetivo="Reuniao institucional",
        quantidade_diarias=Decimal("1.0"),
    )


@pytest.mark.django_db
@pytest.mark.parametrize("builder", [_novo_reembolso, _novo_jeton, _novo_auxilio])
def test_definir_status_normaliza_e_nao_duplica_por_case(processo_factory, builder):
    processo = processo_factory()
    beneficiario = _credor_pf()
    verba = builder(processo, beneficiario)

    verba.definir_status("solicitada")
    verba.refresh_from_db()

    assert verba.status is not None
    assert verba.status.status_choice == "SOLICITADA"

    verba.definir_status("SOLICITADA")
    assert StatusChoicesVerbasIndenizatorias.objects.filter(status_choice__iexact="SOLICITADA").count() == 1


@pytest.mark.django_db
def test_definir_status_sincroniza_autorizada_em_diaria(processo_factory):
    processo = processo_factory()
    beneficiario = _credor_pf()
    diaria = _nova_diaria(processo, beneficiario)

    diaria.definir_status("aprovada", autorizada=True)
    diaria.refresh_from_db()
    assert diaria.status.status_choice == "APROVADA"
    assert diaria.autorizada is True

    diaria.definir_status("solicitada", autorizada=False)
    diaria.refresh_from_db()
    assert diaria.status.status_choice == "SOLICITADA"
    assert diaria.autorizada is False


@pytest.mark.django_db
def test_definir_status_rejeita_status_vazio(processo_factory):
    processo = processo_factory()
    beneficiario = _credor_pf()
    reembolso = _novo_reembolso(processo, beneficiario)

    with pytest.raises(ValidationError):
        reembolso.definir_status("   ")
