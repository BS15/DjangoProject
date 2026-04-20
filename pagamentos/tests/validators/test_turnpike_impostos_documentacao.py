from datetime import date
from decimal import Decimal

import pytest
from django.core.files.base import ContentFile

from fiscal.models import CodigosImposto, DocumentoPagamentoImposto, RetencaoImposto
from pagamentos.validators import verificar_turnpike


@pytest.mark.django_db
def test_turnpike_bloqueia_quando_retencao_sem_documento_pagamento(
    processo_factory,
    add_nota_fiscal,
    add_documento_processo,
    add_comprovante,
):
    processo = processo_factory(
        status="LANÇADO - AGUARDANDO COMPROVANTE",
        tipo_pagamento_nome="IMPOSTOS",
    )
    processo.valor_liquido = Decimal("100.00")
    processo.save(update_fields=["valor_liquido"])

    add_documento_processo(
        processo,
        tipo_nome="COMPROVANTE DE PAGAMENTO",
        nome_arquivo="comprovante_lastro.pdf",
    )
    add_comprovante(processo, valor_pago=Decimal("100.00"))

    nota = add_nota_fiscal(processo, atestada=True)
    codigo = CodigosImposto.objects.create(codigo="1708", regra_competencia="emissao")
    RetencaoImposto.objects.create(
        nota_fiscal=nota,
        codigo=codigo,
        valor=Decimal("10.00"),
        competencia=date(2026, 4, 1),
        processo_pagamento=processo,
    )

    erros = verificar_turnpike(
        processo,
        "LANÇADO - AGUARDANDO COMPROVANTE",
        "PAGO - EM CONFERÊNCIA",
    )

    assert any("DocumentoPagamentoImposto" in erro for erro in erros)


@pytest.mark.django_db
def test_turnpike_permite_quando_todas_retencoes_tem_documentacao_completa(
    processo_factory,
    add_nota_fiscal,
    add_documento_processo,
    add_comprovante,
    pdf_bytes,
):
    processo = processo_factory(
        status="LANÇADO - AGUARDANDO COMPROVANTE",
        tipo_pagamento_nome="IMPOSTOS",
    )
    processo.valor_liquido = Decimal("100.00")
    processo.save(update_fields=["valor_liquido"])

    add_documento_processo(
        processo,
        tipo_nome="COMPROVANTE DE PAGAMENTO",
        nome_arquivo="comprovante_lastro.pdf",
    )
    add_comprovante(processo, valor_pago=Decimal("100.00"))

    nota = add_nota_fiscal(processo, atestada=True)
    codigo = CodigosImposto.objects.create(codigo="1708", regra_competencia="emissao")
    retencao = RetencaoImposto.objects.create(
        nota_fiscal=nota,
        codigo=codigo,
        valor=Decimal("10.00"),
        competencia=date(2026, 4, 1),
        processo_pagamento=processo,
    )

    DocumentoPagamentoImposto.objects.create(
        retencao=retencao,
        codigo_imposto=codigo,
        competencia=date(2026, 4, 1),
        relatorio_retencoes=ContentFile(pdf_bytes, name="relatorio.pdf"),
        guia_recolhimento=ContentFile(pdf_bytes, name="guia.pdf"),
        comprovante_pagamento=ContentFile(pdf_bytes, name="comprovante.pdf"),
    )

    erros = verificar_turnpike(
        processo,
        "LANÇADO - AGUARDANDO COMPROVANTE",
        "PAGO - EM CONFERÊNCIA",
    )

    assert not any("DocumentoPagamentoImposto" in erro for erro in erros)
