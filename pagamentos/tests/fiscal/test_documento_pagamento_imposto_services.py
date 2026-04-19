from datetime import date
from decimal import Decimal

import pytest

from fiscal.models import CodigosImposto, DocumentoPagamentoImposto, RetencaoImposto
from fiscal.services.impostos import (
    criar_documentos_pagamento_impostos,
    verificar_completude_documentos_impostos,
)


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
