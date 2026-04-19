from decimal import Decimal

import pytest

from fluxo.domain_models import ProcessoStatus
from fluxo.validators import verificar_turnpike


@pytest.mark.django_db
@pytest.mark.parametrize(
    "valor_liquido,soma_comprovantes,espera_bloqueio",
    [
        (Decimal("100.00"), [Decimal("100.00")], False),  # BX-02
        (Decimal("100.00"), [Decimal("99.99")], False),   # BX-03
        (Decimal("100.00"), [Decimal("99.9899")], True),  # BX-04
        (Decimal("100.00"), [Decimal("99.98")], True),    # BX-05
    ],
)
def test_baixa_bancaria_tolerancia_decimal(
    processo_factory,
    add_comprovante,
    add_documento_processo,
    monkeypatch,
    valor_liquido,
    soma_comprovantes,
    espera_bloqueio,
):
    processo = processo_factory(status=ProcessoStatus.LANCADO_AGUARDANDO_COMPROVANTE)
    processo.valor_liquido = valor_liquido
    processo.save(update_fields=["valor_liquido"])

    # Garante somente o lastro documental exigido pelo turnpike (sem influenciar a soma).
    add_documento_processo(
        processo,
        tipo_nome="COMPROVANTE DE PAGAMENTO",
        nome_arquivo="comprovante_lastro.pdf",
    )

    usa_quarta_casa = any(valor.as_tuple().exponent < -2 for valor in soma_comprovantes)
    if usa_quarta_casa:
        class _Comp:
            def __init__(self, valor_pago):
                self.valor_pago = valor_pago

        monkeypatch.setattr(
            type(processo.comprovantes_pagamento),
            "all",
            lambda self: [_Comp(valor) for valor in soma_comprovantes],
        )
    else:
        for valor in soma_comprovantes:
            add_comprovante(processo, valor_pago=valor)

    erros = verificar_turnpike(
        processo,
        ProcessoStatus.LANCADO_AGUARDANDO_COMPROVANTE,
        ProcessoStatus.PAGO_EM_CONFERENCIA,
    )
    tem_erro_de_soma = any("Soma dos comprovantes" in erro for erro in erros)
    assert tem_erro_de_soma is espera_bloqueio


@pytest.mark.django_db
def test_baixa_bancaria_suprimento_ignora_divergencia_de_valor(processo_factory, add_comprovante):
    processo = processo_factory(
        status=ProcessoStatus.LANCADO_AGUARDANDO_COMPROVANTE,
        tipo_pagamento_nome="SUPRIMENTO",
    )
    processo.valor_liquido = Decimal("100.00")
    processo.save(update_fields=["valor_liquido"])
    add_comprovante(processo, valor_pago=Decimal("10.00"))

    erros = verificar_turnpike(
        processo,
        ProcessoStatus.LANCADO_AGUARDANDO_COMPROVANTE,
        ProcessoStatus.PAGO_EM_CONFERENCIA,
    )
    assert not any("Soma dos comprovantes" in erro for erro in erros)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "cenario,nota_setup,espera_bloqueio",
    [
        ("sem_notas", [], True),
        ("duas_notas_uma_nao_atestada", [True, False], True),
        ("nota_atestada_valor_zero", ["zero"], True),
        ("duas_notas_todas_atestadas", [True, True], False),
    ],
)
def test_liquidacao_exige_lastro_fiscal_robusto(
    processo_factory,
    add_nota_fiscal,
    cenario,
    nota_setup,
    espera_bloqueio,
):
    processo = processo_factory(status=ProcessoStatus.AGUARDANDO_LIQUIDACAO)

    for item in nota_setup:
        if item == "zero":
            add_nota_fiscal(
                processo,
                atestada=True,
                valor_bruto=Decimal("0.00"),
                valor_liquido=Decimal("0.00"),
            )
        else:
            add_nota_fiscal(processo, atestada=bool(item))

    erros = verificar_turnpike(
        processo,
        ProcessoStatus.AGUARDANDO_LIQUIDACAO,
        ProcessoStatus.A_PAGAR_PENDENTE_AUTORIZACAO,
    )

    assert (len(erros) > 0) is espera_bloqueio


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tipo_documento,conteudo,espera_bloqueio",
    [
        (None, None, True),
        ("OUTRO DOCUMENTO", b"arquivo qualquer", True),
        ("DOCUMENTOS ORÇAMENTÁRIOS", b"", True),
        ("DOCUMENTOS ORÇAMENTÁRIOS", b"corrompido", True),
        ("DOCUMENTOS ORÇAMENTÁRIOS", None, False),
    ],
)
def test_gate_orcamentario_estrito(
    processo_factory,
    add_documento_processo,
    tipo_documento,
    conteudo,
    espera_bloqueio,
):
    processo = processo_factory(status=ProcessoStatus.A_EMPENHAR)
    if tipo_documento:
        add_documento_processo(
            processo,
            tipo_nome=tipo_documento,
            conteudo=conteudo,
            nome_arquivo="doc_orcamentario.pdf",
        )

    erros = verificar_turnpike(
        processo,
        ProcessoStatus.A_EMPENHAR,
        ProcessoStatus.AGUARDANDO_LIQUIDACAO,
    )
    assert (len(erros) > 0) is espera_bloqueio
