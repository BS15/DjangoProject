from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

from fiscal.models import (
    CodigosImposto,
    DocumentoPagamentoImposto,
    RetencaoImposto,
)


@pytest.mark.django_db
def test_documento_pagamento_imposto_unicidade_por_retencao_codigo_competencia(processo_factory, add_nota_fiscal, pdf_bytes):
    processo = processo_factory()
    nota = add_nota_fiscal(processo, atestada=True)
    codigo = CodigosImposto.objects.create(codigo="1708", regra_competencia="emissao")
    retencao = RetencaoImposto.objects.create(
        nota_fiscal=nota,
        codigo=codigo,
        valor=Decimal("10.00"),
        competencia=date(2026, 4, 1),
    )

    DocumentoPagamentoImposto.objects.create(
        retencao=retencao,
        codigo_imposto=codigo,
        competencia=date(2026, 4, 1),
        relatorio_retencoes=ContentFile(pdf_bytes, name="relatorio.pdf"),
        guia_recolhimento=ContentFile(pdf_bytes, name="guia.pdf"),
        comprovante_pagamento=ContentFile(pdf_bytes, name="comprovante.pdf"),
    )

    duplicado = DocumentoPagamentoImposto(
        retencao=retencao,
        codigo_imposto=codigo,
        competencia=date(2026, 4, 1),
        relatorio_retencoes=ContentFile(pdf_bytes, name="relatorio_2.pdf"),
        guia_recolhimento=ContentFile(pdf_bytes, name="guia_2.pdf"),
        comprovante_pagamento=ContentFile(pdf_bytes, name="comprovante_2.pdf"),
    )

    with pytest.raises(ValidationError):
        duplicado.full_clean()


@pytest.mark.django_db
def test_documento_pagamento_imposto_consistencia_com_retencao(processo_factory, add_nota_fiscal, pdf_bytes):
    processo = processo_factory()
    nota = add_nota_fiscal(processo, atestada=True)
    codigo_correto = CodigosImposto.objects.create(codigo="1708", regra_competencia="emissao")
    codigo_errado = CodigosImposto.objects.create(codigo="5952", regra_competencia="emissao")
    retencao = RetencaoImposto.objects.create(
        nota_fiscal=nota,
        codigo=codigo_correto,
        valor=Decimal("10.00"),
        competencia=date(2026, 4, 1),
    )

    documento = DocumentoPagamentoImposto(
        retencao=retencao,
        codigo_imposto=codigo_errado,
        competencia=date(2026, 5, 1),
        relatorio_retencoes=ContentFile(pdf_bytes, name="relatorio.pdf"),
        guia_recolhimento=ContentFile(pdf_bytes, name="guia.pdf"),
        comprovante_pagamento=ContentFile(pdf_bytes, name="comprovante.pdf"),
    )

    with pytest.raises(ValidationError) as exc:
        documento.full_clean()

    assert "codigo_imposto" in exc.value.message_dict
    assert "competencia" in exc.value.message_dict


@pytest.mark.django_db
def test_documento_pagamento_imposto_exige_tres_arquivos(processo_factory, add_nota_fiscal, pdf_bytes):
    processo = processo_factory()
    nota = add_nota_fiscal(processo, atestada=True)
    codigo = CodigosImposto.objects.create(codigo="1708", regra_competencia="emissao")
    retencao = RetencaoImposto.objects.create(
        nota_fiscal=nota,
        codigo=codigo,
        valor=Decimal("10.00"),
        competencia=date(2026, 4, 1),
    )

    documento = DocumentoPagamentoImposto(
        retencao=retencao,
        codigo_imposto=codigo,
        competencia=date(2026, 4, 1),
        relatorio_retencoes=ContentFile(pdf_bytes, name="relatorio.pdf"),
        guia_recolhimento=ContentFile(pdf_bytes, name="guia.pdf"),
    )

    with pytest.raises(ValidationError) as exc:
        documento.full_clean()

    assert "comprovante_pagamento" in exc.value.message_dict
