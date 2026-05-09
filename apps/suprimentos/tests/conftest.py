"""Fixtures compartilhadas para testes de suprimentos."""

import io
import uuid
from decimal import Decimal
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from pypdf import PdfWriter

from apps.cadastros.models import Credor
from apps.pagamentos.domain_models import (
    Processo,
    ProcessoStatus,
    StatusChoicesProcesso,
    FormasDePagamento,
    TiposDePagamento,
)
from apps.suprimentos.models import (
    SuprimentoDeFundos,
    DespesaSuprimento,
    StatusChoicesSuprimentoDeFundos,
    DocumentoSuprimentoDeFundos,
    PrestacaoContasSuprimento,
)


def _pdf_bytes(paginas=1):
    """Gera bytes de PDF válido com o número de páginas especificado."""
    writer = PdfWriter()
    for _ in range(paginas):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture
def user_factory(db):
    """Factory para criar usuários de teste."""
    def factory(username_prefix="user"):
        username = f"{username_prefix}_{uuid.uuid4().hex[:8]}"
        return get_user_model().objects.create_user(
            username=username,
            password="x",
            email=f"{username}@example.com",
        )
    return factory


@pytest.fixture
def credor_factory(db):
    """Factory para criar credores (supridores)."""
    def factory(tipo="PF"):
        return Credor.objects.create(
            nome=f"Credor {uuid.uuid4().hex[:6]}",
            cpf_cnpj=f"{uuid.uuid4().int % 10**11:011d}",
            tipo=tipo,
        )
    return factory


@pytest.fixture
def processo_factory(db):
    """Factory para criar processos de pagamento."""
    def factory(*, status=ProcessoStatus.AGUARDANDO_LIQUIDACAO):
        credor = Credor.objects.create(
            nome=f"Credor {uuid.uuid4().hex[:6]}",
            cpf_cnpj=f"{uuid.uuid4().int % 10**11:011d}",
            tipo="PF",
        )
        forma_pagamento = FormasDePagamento.objects.create(
            forma_pagamento=f"PIX-{uuid.uuid4().hex[:6]}"
        )
        tipo_pagamento = TiposDePagamento.objects.create(
            tipo_pagamento=f"SERVICO-{uuid.uuid4().hex[:6]}"
        )
        status_obj, _ = StatusChoicesProcesso.objects.get_or_create(
            opcao_status__iexact=status,
            defaults={"opcao_status": status},
        )
        return Processo.objects.create(
            credor=credor,
            valor_bruto=Decimal("1000.00"),
            valor_liquido=Decimal("1000.00"),
            forma_pagamento=forma_pagamento,
            tipo_pagamento=tipo_pagamento,
            status=status_obj,
        )
    return factory


@pytest.fixture
def status_factory(db):
    """Factory para criar status de suprimento."""
    def factory(status_choice="ABERTO"):
        obj, _ = StatusChoicesSuprimentoDeFundos.objects.get_or_create(
            status_choice=status_choice,
            defaults={"is_active": True}
        )
        return obj
    return factory


@pytest.fixture
def suprimento_factory(db, credor_factory, processo_factory, status_factory):
    """Factory para criar suprimentos de fundos."""
    def factory(
        *,
        valor_liquido=Decimal("500.00"),
        taxa_saque=Decimal("0.00"),
        inicio_periodo=None,
        fim_periodo=None,
        status=None,
        processo=None,
        suprido=None,
    ):
        if inicio_periodo is None:
            inicio_periodo = date.today()
        if fim_periodo is None:
            fim_periodo = date.today() + timedelta(days=30)
        if status is None:
            status = status_factory("ABERTO")
        if suprido is None:
            suprido = credor_factory(tipo="PF")

        return SuprimentoDeFundos.objects.create(
            suprido=suprido,
            valor_liquido=valor_liquido,
            taxa_saque=taxa_saque,
            inicio_periodo=inicio_periodo,
            fim_periodo=fim_periodo,
            status=status,
            processo=processo,
        )
    return factory


@pytest.fixture
def despesa_factory(db, suprimento_factory):
    """Factory para criar despesas de suprimento."""
    def factory(
        *,
        suprimento=None,
        valor=Decimal("100.00"),
        data=None,
        estabelecimento="Estabelecimento Teste",
        cnpj_cpf="12345678901234",
        detalhamento="Material de Consumo",
        nota_fiscal="NF-001",
        arquivo=None,
    ):
        if suprimento is None:
            suprimento = suprimento_factory()
        if data is None:
            data = date.today()

        return DespesaSuprimento.objects.create(
            suprimento=suprimento,
            data=data,
            estabelecimento=estabelecimento,
            cnpj_cpf=cnpj_cpf,
            detalhamento=detalhamento,
            nota_fiscal=nota_fiscal,
            valor=valor,
            arquivo=arquivo,
        )
    return factory


@pytest.fixture
def pdf_bytes():
    """Bytes de PDF válido para anexos."""
    return _pdf_bytes()


@pytest.fixture
def documento_suprimento_factory(db, suprimento_factory, pdf_bytes):
    """Factory para criar documentos de suprimento."""
    def factory(
        *,
        suprimento=None,
        tipo_documento="RECIBO",
        arquivo=None,
        order=1,
    ):
        if suprimento is None:
            suprimento = suprimento_factory()
        if arquivo is None:
            arquivo = ContentFile(pdf_bytes, name=f"{tipo_documento}_{uuid.uuid4().hex[:6]}.pdf")

        return DocumentoSuprimentoDeFundos.objects.create(
            suprimento=suprimento,
            arquivo=arquivo,
            ordem=order,
        )
    return factory


@pytest.fixture
def prestacao_contas_factory(db, suprimento_factory):
    """Factory para criar prestações de contas de suprimento."""
    def factory(
        *,
        suprimento=None,
        status=PrestacaoContasSuprimento.STATUS_ABERTA,
    ):
        if suprimento is None:
            suprimento = suprimento_factory()

        return PrestacaoContasSuprimento.objects.create(
            suprimento=suprimento,
            status=status,
        )
    return factory
