"""Fixtures para a suite de testes de verbas_indenizatorias."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from pypdf import PdfWriter
import io

from credores.models import Credor
from apps.pagamentos.domain_models import (
    FormasDePagamento,
    Processo,
    ProcessoStatus,
    StatusChoicesProcesso,
    TiposDePagamento,
)
from verbas_indenizatorias.models import (
    MeiosDeTransporte,
    StatusChoicesVerbasIndenizatorias,
    TiposDeVerbasIndenizatorias,
)


def _pdf_bytes():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture
def pdf_bytes():
    return _pdf_bytes()


@pytest.fixture
def user_factory(db):
    def factory(prefix="u"):
        name = f"{prefix}_{uuid.uuid4().hex[:8]}"
        return get_user_model().objects.create_user(username=name, password="x", email=f"{name}@t.com")
    return factory


@pytest.fixture
def credor_pf(db):
    return Credor.objects.create(
        nome=f"Beneficiario {uuid.uuid4().hex[:6]}",
        cpf_cnpj=f"{uuid.uuid4().int % 10**11:011d}",
        tipo="PF",
    )


@pytest.fixture
def processo_factory(db):
    def factory(*, status=ProcessoStatus.AGUARDANDO_LIQUIDACAO, tipo_nome="VERBAS INDENIZATORIAS"):
        credor = Credor.objects.create(
            nome=f"Credor {uuid.uuid4().hex[:6]}",
            cpf_cnpj=f"{uuid.uuid4().int % 10**11:011d}",
            tipo="PF",
        )
        forma = FormasDePagamento.objects.create(forma_pagamento=f"PIX-{uuid.uuid4().hex[:6]}")
        tipo_pg = TiposDePagamento.objects.create(tipo_pagamento=f"{tipo_nome}-{uuid.uuid4().hex[:6]}")
        status_obj, _ = StatusChoicesProcesso.objects.get_or_create(
            opcao_status__iexact=status,
            defaults={"opcao_status": status},
        )
        return Processo.objects.create(
            credor=credor,
            valor_bruto=Decimal("500.00"),
            valor_liquido=Decimal("500.00"),
            forma_pagamento=forma,
            tipo_pagamento=tipo_pg,
            status=status_obj,
        )
    return factory


@pytest.fixture
def meio_transporte(db):
    obj, _ = MeiosDeTransporte.objects.get_or_create(meio_de_transporte="VEICULO PROPRIO")
    return obj


@pytest.fixture
def tipo_verba(db):
    obj, _ = TiposDeVerbasIndenizatorias.objects.get_or_create(
        tipo_verba="DIARIA",
        defaults={"is_active": True},
    )
    return obj


@pytest.fixture
def diaria_factory(db, user_factory, meio_transporte):
    """Factory que cria Diaria com beneficiário único por instância para evitar conflitos de data."""
    call_count = {"n": 0}

    def factory(processo=None, *, status="RASCUNHO", dias=1, numero_siscac=None):
        call_count["n"] += 1
        beneficiario = Credor.objects.create(
            nome=f"Beneficiario {uuid.uuid4().hex[:8]}",
            cpf_cnpj=f"{uuid.uuid4().int % 10**11:011d}",
            tipo="PF",
        )
        user = user_factory()
        status_obj, _ = StatusChoicesVerbasIndenizatorias.objects.get_or_create(
            status_choice__iexact=status,
            defaults={"status_choice": status},
        )
        from verbas_indenizatorias.models import Diaria
        from datetime import date, timedelta
        base_date = date(2026, 4, 1) + timedelta(days=(call_count["n"] - 1) * 30)
        d = Diaria(
            processo=processo,
            beneficiario=beneficiario,
            proponente=user,
            criado_por=user,
            tipo_solicitacao="INICIAL",
            data_saida=base_date,
            data_retorno=base_date + timedelta(days=max(0, dias - 1)),
            cidade_origem="BRASILIA",
            cidade_destino="SAO PAULO",
            objetivo="Reuniao de trabalho",
            quantidade_diarias=Decimal(str(dias)),
            meio_de_transporte=meio_transporte,
            status=status_obj,
            numero_siscac=numero_siscac,
        )
        d._bypass_domain_seal = True
        d.save()
        return d
    return factory
