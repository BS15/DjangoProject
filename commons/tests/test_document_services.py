"""Testes de integração para commons/shared/document_services.py."""

import pytest

from commons.shared.document_services import obter_ou_criar_tipo_documento, obter_proxima_ordem_documento


# --- obter_proxima_ordem_documento ---

@pytest.mark.django_db
def test_proxima_ordem_sem_documentos(processo_factory):
    processo = processo_factory()
    proxima = obter_proxima_ordem_documento(processo.documentos)
    assert proxima == 1


@pytest.mark.django_db
def test_proxima_ordem_com_documentos(processo_factory, add_documento_processo):
    processo = processo_factory()
    add_documento_processo(processo, tipo_nome="BOLETO")
    add_documento_processo(processo, tipo_nome="BOLETO", nome_arquivo="doc2.pdf")
    proxima = obter_proxima_ordem_documento(processo.documentos)
    assert proxima == 3


# --- obter_ou_criar_tipo_documento ---

@pytest.mark.django_db
def test_cria_tipo_quando_nao_existe(processo_factory):
    from pagamentos.domain_models import TiposDocumento
    processo = processo_factory()
    nome = "TIPO UNICO XPTO"
    tipo = obter_ou_criar_tipo_documento(nome, tipo_pagamento=processo.tipo_pagamento)
    assert tipo is not None
    assert tipo.tipo_documento.upper() == nome.upper()


@pytest.mark.django_db
def test_retorna_tipo_especifico_quando_existe(processo_factory):
    from pagamentos.domain_models import TiposDocumento
    processo = processo_factory()
    nome = "NOTA FISCAL SERVICO"
    TiposDocumento.objects.create(tipo_documento=nome, tipo_pagamento=processo.tipo_pagamento)
    tipo = obter_ou_criar_tipo_documento(nome, tipo_pagamento=processo.tipo_pagamento)
    assert tipo is not None
    assert TiposDocumento.objects.filter(tipo_documento__iexact=nome).count() == 1


@pytest.mark.django_db
def test_retorna_tipo_geral_quando_especifico_nao_existe(processo_factory):
    from pagamentos.domain_models import TiposDocumento
    processo = processo_factory()
    nome = "RECIBO PADRAO"
    TiposDocumento.objects.create(tipo_documento=nome, tipo_pagamento=None)
    tipo = obter_ou_criar_tipo_documento(nome, tipo_pagamento=processo.tipo_pagamento)
    assert tipo is not None
    assert tipo.tipo_pagamento is None


@pytest.mark.django_db
def test_sem_tipo_pagamento_usa_tipo_geral():
    from pagamentos.domain_models import TiposDocumento
    nome = "DOCUMENTO GERAL ABC"
    TiposDocumento.objects.create(tipo_documento=nome, tipo_pagamento=None)
    tipo = obter_ou_criar_tipo_documento(nome)
    assert tipo is not None
    assert tipo.tipo_documento.upper() == nome.upper()


@pytest.mark.django_db
def test_case_insensitive_lookup(processo_factory):
    from pagamentos.domain_models import TiposDocumento
    processo = processo_factory()
    TiposDocumento.objects.create(tipo_documento="CONTRATO DE SERVICO", tipo_pagamento=None)
    tipo = obter_ou_criar_tipo_documento("contrato de servico")
    assert tipo is not None
    assert TiposDocumento.objects.filter(tipo_documento__iexact="contrato de servico").count() == 1
