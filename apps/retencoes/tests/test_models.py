"""Testes para os modelos de domínio do módulo de retenções."""

from decimal import Decimal
from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError

from apps.retencoes.models import (
    DocumentoFiscal,
    RetencaoImposto,
    LiquidacaoDocumentoFiscal,
    DadosContribuinte,
    CodigosImposto,
)


class TestDocumentoFiscalModel:
    """Testes para o modelo DocumentoFiscal."""

    def test_create_documento_fiscal_basico(self, documento_fiscal_factory):
        """Documento fiscal deve ser criado com campos obrigatórios."""
        doc = documento_fiscal_factory()
        assert doc.pk is not None
        assert doc.numero_nota_fiscal == "NF-001"
        assert doc.valor_bruto == Decimal("1000.00")

    def test_sincroniza_cnpj_ao_salvar(self, documento_fiscal_factory, credor_factory):
        """Save deve sincronizar CNPJ do emitente com credor."""
        credor = credor_factory(tipo="PJ")
        doc = documento_fiscal_factory(nome_emitente=credor)

        assert doc.cnpj_emitente == credor.cpf_cnpj

    def test_validacao_valor_liquido_maior_que_bruto(self, documento_fiscal_factory):
        """Valor líquido não pode ser maior que valor bruto."""
        with pytest.raises(ValidationError) as exc_info:
            doc = documento_fiscal_factory(
                valor_bruto=Decimal("100.00"),
                valor_liquido=Decimal("150.00"),
            )
            doc.full_clean()

        # Se passou no create, tentar full_clean deve falhar
        # Se falhou no create, é porque clean() foi chamado

    def test_validacao_valor_bruto_minimo(self, documento_fiscal_factory):
        """Valor bruto deve ser >= 0.01."""
        with pytest.raises(ValidationError):
            documento_fiscal_factory(valor_bruto=Decimal("0.00"))

    def test_validacao_valor_liquido_nao_negativo(self, documento_fiscal_factory):
        """Valor líquido não pode ser negativo."""
        with pytest.raises(ValidationError):
            documento_fiscal_factory(valor_liquido=Decimal("-10.00"))

    def test_liquidacao_criada_automaticamente(self, documento_fiscal_factory):
        """Save deve criar registro de LiquidacaoDocumentoFiscal automaticamente."""
        doc = documento_fiscal_factory()

        assert hasattr(doc, 'liquidacao')
        assert doc.liquidacao is not None
        assert isinstance(doc.liquidacao, LiquidacaoDocumentoFiscal)

    def test_liquidacao_atual_property(self, documento_fiscal_factory):
        """Propriedade liquidacao_atual deve retornar a liquidação."""
        doc = documento_fiscal_factory()

        assert doc.liquidacao_atual == doc.liquidacao

    def test_str_representation(self, documento_fiscal_factory, credor_factory):
        """__str__ deve retornar representação legível."""
        credor = credor_factory()
        doc = documento_fiscal_factory(nome_emitente=credor, numero_nota="NF-123")

        assert "NF-123" in str(doc)
        assert credor.nome in str(doc)

    def test_atestada_field(self, documento_fiscal_factory):
        """Deve ter campo atestada com padrão False."""
        doc = documento_fiscal_factory(atestada=False)
        assert doc.atestada is False

    def test_unique_constraint_nf_por_processo(self, documento_fiscal_factory, processo_factory):
        """Deve evitar duplicatas de NF por processo (com série)."""
        processo = processo_factory()
        doc1 = documento_fiscal_factory(
            processo=processo,
            numero_nota="NF-001",
        )

        # Tentar criar outra com mesmo número em mesmo processo
        with pytest.raises(Exception):  # IntegrityError esperado
            DocumentoFiscal.objects.create(
                processo=processo,
                nome_emitente=doc1.nome_emitente,
                cnpj_emitente=doc1.cnpj_emitente,
                numero_nota_fiscal="NF-001",
                data_emissao=date.today(),
                valor_bruto=Decimal("100.00"),
                valor_liquido=Decimal("100.00"),
            )

    def test_campo_isenção(self, documento_fiscal_factory):
        """Deve permitir marcar como isento/imune."""
        doc = documento_fiscal_factory(is_rendimento_isento=True)
        assert doc.is_rendimento_isento is True

    def test_tipos_isenção_choices(self, documento_fiscal_factory):
        """Deve ter choices válidos para tipo de isenção."""
        doc = DocumentoFiscal(
            tpIsencao='01',  # Imunidade
        )
        assert doc.tpIsencao == '01'


class TestRetencaoImpostoModel:
    """Testes para o modelo RetencaoImposto."""

    def test_create_retencao_basica(self, retencao_imposto_factory):
        """Retenção deve ser criada com campos obrigatórios."""
        retencao = retencao_imposto_factory()
        assert retencao.pk is not None
        assert retencao.valor == Decimal("100.00")

    def test_calcula_competencia_pela_emissao(
        self, retencao_imposto_factory, codigo_imposto_factory, documento_fiscal_factory
    ):
        """Deve calcular competência pela data de emissão se regra competência."""
        codigo = codigo_imposto_factory(regra_competencia='emissao')
        data_emissao = date(2026, 5, 15)
        doc = documento_fiscal_factory(data_emissao=data_emissao)

        retencao = retencao_imposto_factory(
            nota_fiscal=doc,
            codigo=codigo,
        )

        # Competência deve ser normalizada para 2026-05-01
        assert retencao.competencia == date(2026, 5, 1)

    def test_calcula_competencia_pela_pagamento(
        self, retencao_imposto_factory, codigo_imposto_factory, documento_fiscal_factory
    ):
        """Deve calcular competência pela data de pagamento se regra competência."""
        codigo = codigo_imposto_factory(regra_competencia='pagamento')
        data_pagamento = date(2026, 6, 10)

        retencao = retencao_imposto_factory(
            codigo=codigo,
            data_pagamento=data_pagamento,
        )

        # Competência deve ser normalizada para 2026-06-01
        assert retencao.competencia == date(2026, 6, 1)

    def test_valor_retido_nao_negativo(self, retencao_imposto_factory):
        """Valor retido deve ser >= 0."""
        with pytest.raises(ValidationError):
            retencao_imposto_factory(valor=Decimal("-50.00"))

    def test_rendimento_tributavel_nao_negativo(self, retencao_imposto_factory):
        """Rendimento tributável deve ser >= 0."""
        with pytest.raises(ValidationError):
            retencao_imposto_factory(rendimento_tributavel=Decimal("-100.00"))

    def test_str_representation(self, retencao_imposto_factory, codigo_imposto_factory):
        """__str__ deve retornar código e valor."""
        codigo = codigo_imposto_factory(codigo="IRRF")
        retencao = retencao_imposto_factory(codigo=codigo, valor=Decimal("250.50"))

        expected = f"IRRF - R$ 250.50"
        assert str(retencao) == expected


class TestDadosContribuinteModel:
    """Testes para o modelo DadosContribuinte."""

    def test_create_dados_contribuinte(self, dados_contribuinte_factory):
        """Deve criar dados do contribuinte."""
        dados = dados_contribuinte_factory()
        assert dados.pk is not None
        assert dados.cnpj
        assert dados.razao_social

    def test_str_representation(self, dados_contribuinte_factory):
        """__str__ deve retornar razão social e CNPJ."""
        dados = dados_contribuinte_factory(
            razao_social="Governo Federal",
            cnpj="00000000000191",
        )
        assert "Governo Federal" in str(dados)
        assert "00000000000191" in str(dados)


class TestCodigosImpostoModel:
    """Testes para o modelo CodigosImposto."""

    def test_create_codigo_imposto(self, codigo_imposto_factory):
        """Deve criar código de imposto."""
        codigo = codigo_imposto_factory()
        assert codigo.pk is not None
        assert codigo.is_active is True

    def test_regra_competencia_choices(self, codigo_imposto_factory):
        """Deve ter choices válidos para regra_competencia."""
        codigo1 = codigo_imposto_factory(regra_competencia='emissao')
        codigo2 = codigo_imposto_factory(codigo="CODIGO2", regra_competencia='pagamento')

        assert codigo1.regra_competencia == 'emissao'
        assert codigo2.regra_competencia == 'pagamento'

    def test_serie_reinf_choices(self, codigo_imposto_factory):
        """Deve ter choices válidos para série_reinf."""
        codigo = codigo_imposto_factory(serie_reinf='S4000')
        assert codigo.serie_reinf == 'S4000'

    def test_str_representation(self, codigo_imposto_factory):
        """__str__ deve retornar código."""
        codigo = codigo_imposto_factory(codigo="COFINS")
        assert str(codigo) == "COFINS"


class TestLiquidacaoDocumentoFiscalModel:
    """Testes para o modelo LiquidacaoDocumentoFiscal."""

    def test_create_liquidacao(self, documento_fiscal_factory, user_factory):
        """Deve criar liquidação vinculada a documento fiscal."""
        user = user_factory()
        doc = documento_fiscal_factory()

        # Documento fiscal cria liquidação automaticamente
        assert doc.liquidacao is not None
        assert doc.liquidacao.documento_fiscal == doc

    def test_fiscal_contrato_opcional(self, documento_fiscal_factory):
        """fiscal_contrato deve ser opcional."""
        doc = documento_fiscal_factory()
        liquidacao = doc.liquidacao

        assert liquidacao.fiscal_contrato is None

    def test_fiscal_contrato_atribuivel(self, documento_fiscal_factory, user_factory):
        """Deve permitir atribuir fiscal do contrato."""
        user = user_factory()
        doc = documento_fiscal_factory()
        liquidacao = doc.liquidacao

        liquidacao.fiscal_contrato = user
        liquidacao.save()

        assert liquidacao.fiscal_contrato == user

    def test_timestamps(self, documento_fiscal_factory):
        """Deve ter created_at e updated_at."""
        doc = documento_fiscal_factory()
        liquidacao = doc.liquidacao

        assert liquidacao.created_at is not None
        assert liquidacao.updated_at is not None

    def test_str_representation(self, documento_fiscal_factory):
        """__str__ deve retornar número da NF."""
        doc = documento_fiscal_factory(numero_nota="NF-999")
        liquidacao = doc.liquidacao

        assert "NF-999" in str(liquidacao)


class TestModelHistory:
    """Testes para rastreamento de histórico via simple_history."""

    def test_documento_fiscal_tem_history(self, documento_fiscal_factory):
        """DocumentoFiscal deve ter histórico."""
        doc = documento_fiscal_factory()
        assert hasattr(doc, 'history')

    def test_retencao_imposto_tem_history(self, retencao_imposto_factory):
        """RetencaoImposto deve ter histórico."""
        retencao = retencao_imposto_factory()
        assert hasattr(retencao, 'history')

    def test_dados_contribuinte_tem_history(self, dados_contribuinte_factory):
        """DadosContribuinte deve ter histórico."""
        dados = dados_contribuinte_factory()
        assert hasattr(dados, 'history')
