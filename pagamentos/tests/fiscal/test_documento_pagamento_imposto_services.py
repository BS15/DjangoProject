import io
from datetime import date
from decimal import Decimal

import pytest
from pypdf import PdfReader

from fiscal.models import CodigosImposto, DocumentoPagamentoImposto, RetencaoImposto
from fiscal.services.impostos import (
    DOC_RELATORIO_AGRUPAMENTO,
    anexar_relatorio_agrupamento_retencoes_no_processo,
    criar_documentos_pagamento_impostos,
    gerar_relatorio_retencoes_agrupamento_pdf,
    verificar_completude_documentos_impostos,
)
from pagamentos.domain_models import DocumentoProcesso


@pytest.mark.django_db
def test_criar_documentos_pagamento_impostos_em_lote(processo_factory, add_nota_fiscal, pdf_bytes):
    processo = processo_factory(tipo_pagamento_nome="IMPOSTOS")
    nota = add_nota_fiscal(processo, atestada=True)
    codigo = CodigosImposto.objects.create(codigo="1708", regra_competencia="emissao")

    ret_1 = RetencaoImposto.objects.create(
        nota_fiscal=nota,
        codigo=codigo,
        valor=Decimal("10.00"),
        competencia=date(2026, 4, 1),
    )
    ret_2 = RetencaoImposto.objects.create(
        nota_fiscal=nota,
        codigo=codigo,
        valor=Decimal("20.00"),
        competencia=date(2026, 4, 1),
    )

    criados = criar_documentos_pagamento_impostos(
        retencoes=[ret_1, ret_2],
        relatorio_bytes=pdf_bytes,
        relatorio_nome="relatorio.pdf",
        guia_bytes=pdf_bytes,
        guia_nome="guia.pdf",
        comprovante_bytes=pdf_bytes,
        comprovante_nome="comprovante.pdf",
        competencia=date(2026, 4, 1),
    )

    assert set(criados) == {ret_1.id, ret_2.id}
    assert DocumentoPagamentoImposto.objects.filter(retencao__in=[ret_1, ret_2]).count() == 2


@pytest.mark.django_db
def test_verificar_completude_documentos_impostos_por_processo(processo_factory, add_nota_fiscal, pdf_bytes):
    processo = processo_factory(tipo_pagamento_nome="IMPOSTOS")
    nota = add_nota_fiscal(processo, atestada=True)
    codigo = CodigosImposto.objects.create(codigo="1708", regra_competencia="emissao")

    ret_1 = RetencaoImposto.objects.create(
        nota_fiscal=nota,
        codigo=codigo,
        valor=Decimal("10.00"),
        competencia=date(2026, 4, 1),
        processo_pagamento=processo,
    )
    ret_2 = RetencaoImposto.objects.create(
        nota_fiscal=nota,
        codigo=codigo,
        valor=Decimal("20.00"),
        competencia=date(2026, 4, 1),
        processo_pagamento=processo,
    )

    criar_documentos_pagamento_impostos(
        retencoes=[ret_1],
        relatorio_bytes=pdf_bytes,
        relatorio_nome="relatorio.pdf",
        guia_bytes=pdf_bytes,
        guia_nome="guia.pdf",
        comprovante_bytes=pdf_bytes,
        comprovante_nome="comprovante.pdf",
        competencia=date(2026, 4, 1),
    )

    pendentes = verificar_completude_documentos_impostos(processo)
    assert pendentes == [ret_2.id]

    criar_documentos_pagamento_impostos(
        retencoes=[ret_2],
        relatorio_bytes=pdf_bytes,
        relatorio_nome="relatorio.pdf",
        guia_bytes=pdf_bytes,
        guia_nome="guia.pdf",
        comprovante_bytes=pdf_bytes,
        comprovante_nome="comprovante.pdf",
        competencia=date(2026, 4, 1),
    )

    assert verificar_completude_documentos_impostos(processo) == []


@pytest.mark.django_db
def test_gerar_relatorio_retencoes_agrupamento_pdf_contem_campos_canonicos(processo_factory, add_nota_fiscal):
    processo = processo_factory(tipo_pagamento_nome="IMPOSTOS")
    nota = add_nota_fiscal(processo, atestada=True)
    codigo = CodigosImposto.objects.create(codigo="5952", regra_competencia="emissao")
    retencao = RetencaoImposto.objects.create(
        nota_fiscal=nota,
        codigo=codigo,
        valor=Decimal("15.00"),
        rendimento_tributavel=Decimal("150.00"),
        competencia=date(2026, 4, 1),
        processo_pagamento=processo,
    )

    pdf_bytes = gerar_relatorio_retencoes_agrupamento_pdf([retencao], processo.id)
    texto = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf_bytes)).pages)

    assert "id, nota_fiscal, beneficiario, rendimento_tributavel, data_pagamento, codigo, valor, status, processo_pagamento, competencia" in texto
    assert f"processo_pagamento: {processo.id}" in texto


@pytest.mark.django_db
def test_anexar_relatorio_agrupamento_retencoes_no_processo_insere_na_ordem_1(
    processo_factory,
    add_nota_fiscal,
    add_documento_processo,
):
    processo = processo_factory(tipo_pagamento_nome="IMPOSTOS")
    nota = add_nota_fiscal(processo, atestada=True)
    codigo = CodigosImposto.objects.create(codigo="1708", regra_competencia="emissao")
    retencao = RetencaoImposto.objects.create(
        nota_fiscal=nota,
        codigo=codigo,
        valor=Decimal("10.00"),
        competencia=date(2026, 4, 1),
        processo_pagamento=processo,
    )
    doc_preexistente = add_documento_processo(
        processo,
        tipo_nome="DOCUMENTO EXISTENTE",
        nome_arquivo="existente.pdf",
    )

    documento_relatorio = anexar_relatorio_agrupamento_retencoes_no_processo(
        processo=processo,
        retencoes=[retencao],
    )

    doc_preexistente.refresh_from_db()
    documento_relatorio.refresh_from_db()

    assert DocumentoProcesso.objects.filter(processo=processo).count() == 2
    assert documento_relatorio.ordem == 1
    assert doc_preexistente.ordem == 2
    assert documento_relatorio.tipo.tipo_de_documento == DOC_RELATORIO_AGRUPAMENTO
    assert documento_relatorio.arquivo.name.lower().endswith(".pdf")
