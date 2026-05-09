"""Fixtures compartilhadas para testes de retenções."""

import uuid
from decimal import Decimal
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model

from apps.cadastros.models import Credor
from apps.pagamentos.domain_models import (
    Processo,
    ProcessoStatus,
    StatusChoicesProcesso,
    FormasDePagamento,
    TiposDePagamento,
)
from apps.retencoes.models import (
    DadosContribuinte,
    CodigosImposto,
    StatusChoicesRetencoes,
    DocumentoFiscal,
    LiquidacaoDocumentoFiscal,
    RetencaoImposto,
)


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
    """Factory para criar credores."""
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
def dados_contribuinte_factory(db):
    """Factory para criar dados do contribuinte."""
    def factory(cnpj=None, razao_social="Estados Unidos Brasil"):
        if cnpj is None:
            cnpj = f"{uuid.uuid4().int % 10**10:010d}{uuid.uuid4().int % 10**4:04d}"
        return DadosContribuinte.objects.create(
            cnpj=cnpj,
            razao_social=razao_social,
            tipo_inscricao=1,
        )
    return factory


@pytest.fixture
def codigo_imposto_factory(db):
    """Factory para criar códigos de imposto."""
    def factory(
        codigo="1234",
        regra_competencia="emissao",
        aliquota=None,
        serie_reinf="NONE",
    ):
        return CodigosImposto.objects.create(
            codigo=codigo,
            regra_competencia=regra_competencia,
            aliquota=Decimal(aliquota) if aliquota else None,
            is_active=True,
            serie_reinf=serie_reinf,
        )
    return factory


@pytest.fixture
def status_retencao_factory(db):
    """Factory para criar status de retenção."""
    def factory(status_choice="ABERTA"):
        obj, _ = StatusChoicesRetencoes.objects.get_or_create(
            status_choice=status_choice,
            defaults={"is_active": True}
        )
        return obj
    return factory


@pytest.fixture
def documento_fiscal_factory(db, processo_factory, credor_factory):
    """Factory para criar documentos fiscais."""
    def factory(
        *,
        numero_nota="NF-001",
        valor_bruto=Decimal("1000.00"),
        valor_liquido=Decimal("900.00"),
        data_emissao=None,
        atestada=False,
        processo=None,
        nome_emitente=None,
    ):
        if data_emissao is None:
            data_emissao = date.today()
        if processo is None:
            processo = processo_factory()
        if nome_emitente is None:
            nome_emitente = credor_factory(tipo="PJ")

        return DocumentoFiscal.objects.create(
            processo=processo,
            nome_emitente=nome_emitente,
            cnpj_emitente=nome_emitente.cpf_cnpj,
            numero_nota_fiscal=numero_nota,
            data_emissao=data_emissao,
            valor_bruto=valor_bruto,
            valor_liquido=valor_liquido,
            atestada=atestada,
        )
    return factory


@pytest.fixture
def retencao_imposto_factory(db, documento_fiscal_factory, codigo_imposto_factory, credor_factory):
    """Factory para criar retenções de imposto."""
    def factory(
        *,
        nota_fiscal=None,
        valor=Decimal("100.00"),
        beneficiario=None,
        codigo=None,
        data_pagamento=None,
    ):
        if nota_fiscal is None:
            nota_fiscal = documento_fiscal_factory()
        if beneficiario is None:
            beneficiario = credor_factory()
        if codigo is None:
            codigo = codigo_imposto_factory()
        if data_pagamento is None:
            data_pagamento = date.today()

        return RetencaoImposto.objects.create(
            nota_fiscal=nota_fiscal,
            beneficiario=beneficiario,
            codigo=codigo,
            valor=valor,
            data_pagamento=data_pagamento,
            rendimento_tributavel=Decimal("1000.00"),
        )
    return factory
