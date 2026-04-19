import io
import uuid
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from pypdf import PdfWriter

from credores.models import Credor
from fiscal.models import DocumentoFiscal
from pagamentos.domain_models import (
    ComprovanteDePagamento,
    DocumentoProcesso,
    FormasDePagamento,
    Processo,
    ProcessoStatus,
    StatusChoicesProcesso,
    TiposDeDocumento,
    TiposDePagamento,
)


def _pdf_bytes(paginas=1):
    writer = PdfWriter()
    for _ in range(paginas):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture
def pdf_bytes():
    return _pdf_bytes()


@pytest.fixture
def user_factory(db):
    def factory(username_prefix="user"):
        username = f"{username_prefix}_{uuid.uuid4().hex[:8]}"
        return get_user_model().objects.create_user(
            username=username,
            password="x",
            email=f"{username}@example.com",
        )

    return factory


@pytest.fixture
def processo_factory(db):
    def factory(*, status=ProcessoStatus.AGUARDANDO_LIQUIDACAO, tipo_pagamento_nome="SERVICO"):
        credor = Credor.objects.create(
            nome=f"Credor {uuid.uuid4().hex[:6]}",
            cpf_cnpj=f"{uuid.uuid4().int % 10**11:011d}",
            tipo="PF",
        )
        forma_pagamento = FormasDePagamento.objects.create(
            forma_de_pagamento=f"PIX-{uuid.uuid4().hex[:6]}"
        )
        tipo_pagamento = TiposDePagamento.objects.create(
            tipo_de_pagamento=f"{tipo_pagamento_nome}-{uuid.uuid4().hex[:6]}"
        )
        status_obj, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact=status,
            defaults={"status_choice": status},
        )
        return Processo.objects.create(
            credor=credor,
            valor_bruto=Decimal("100.00"),
            valor_liquido=Decimal("100.00"),
            forma_pagamento=forma_pagamento,
            tipo_pagamento=tipo_pagamento,
            status=status_obj,
        )

    return factory


@pytest.fixture
def tipo_documento_factory(db):
    def factory(nome, *, tipo_pagamento=None):
        return TiposDeDocumento.objects.create(
            tipo_de_documento=nome,
            tipo_de_pagamento=tipo_pagamento,
        )

    return factory


@pytest.fixture
def add_documento_processo(db, tipo_documento_factory, pdf_bytes):
    def factory(processo, *, tipo_nome, conteudo=None, nome_arquivo=None):
        tipo = TiposDeDocumento.objects.filter(
            tipo_de_documento__iexact=tipo_nome,
            tipo_de_pagamento=processo.tipo_pagamento,
        ).first() or tipo_documento_factory(tipo_nome, tipo_pagamento=processo.tipo_pagamento)

        if conteudo is None:
            conteudo = pdf_bytes
        if nome_arquivo is None:
            nome_arquivo = f"{tipo_nome.lower().replace(' ', '_')}_{uuid.uuid4().hex[:6]}.pdf"

        return DocumentoProcesso.objects.create(
            processo=processo,
            tipo=tipo,
            ordem=(processo.documentos.count() + 1),
            arquivo=ContentFile(conteudo, name=nome_arquivo),
        )

    return factory


@pytest.fixture
def add_comprovante(db, tipo_documento_factory, pdf_bytes):
    def factory(processo, *, valor_pago):
        tipo = TiposDeDocumento.objects.filter(
            tipo_de_documento__iexact="COMPROVANTE DE PAGAMENTO",
            tipo_de_pagamento=processo.tipo_pagamento,
        ).first() or tipo_documento_factory("COMPROVANTE DE PAGAMENTO", tipo_pagamento=processo.tipo_pagamento)

        nome = f"comprovante_{uuid.uuid4().hex[:8]}.pdf"
        DocumentoProcesso.objects.create(
            processo=processo,
            tipo=tipo,
            ordem=(processo.documentos.count() + 1),
            arquivo=ContentFile(pdf_bytes, name=nome),
        )

        return ComprovanteDePagamento.objects.create(
            processo=processo,
            tipo=tipo,
            ordem=1,
            arquivo=ContentFile(pdf_bytes, name=nome),
            valor_pago=Decimal(valor_pago),
            numero_comprovante=uuid.uuid4().hex[:10],
        )

    return factory


@pytest.fixture
def add_nota_fiscal(db):
    def factory(processo, *, atestada, valor_bruto=Decimal("100.00"), valor_liquido=Decimal("100.00")):
        return DocumentoFiscal.objects.create(
            processo=processo,
            nome_emitente=processo.credor,
            cnpj_emitente=processo.credor.cpf_cnpj,
            numero_nota_fiscal=uuid.uuid4().hex[:12],
            data_emissao="2026-04-01",
            valor_bruto=Decimal(valor_bruto),
            valor_liquido=Decimal(valor_liquido),
            atestada=atestada,
        )

    return factory
