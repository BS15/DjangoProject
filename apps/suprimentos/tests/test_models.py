"""Testes para os modelos de domínio do módulo de suprimentos."""

from decimal import Decimal
from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError

from apps.suprimentos.models import (
    SuprimentoDeFundos,
    DespesaSuprimento,
    SealedMutationQuerySet,
    PrestacaoContasSuprimento,
)


class TestSuprimentoDeFundosModel:
    """Testes para o modelo SuprimentoDeFundos."""

    def test_create_suprimento_basico(self, suprimento_factory):
        """Suprimento deve ser criado com campos obrigatórios."""
        suprimento = suprimento_factory()
        assert suprimento.pk is not None
        assert suprimento.valor_liquido == Decimal("500.00")
        assert suprimento.status.status_choice == "ABERTO"

    def test_valor_gasto_property(self, suprimento_factory, despesa_factory):
        """Propriedade valor_gasto deve somar despesas vinculadas."""
        suprimento = suprimento_factory(valor_liquido=Decimal("1000.00"))
        despesa_factory(suprimento=suprimento, valor=Decimal("300.00"))
        despesa_factory(suprimento=suprimento, valor=Decimal("200.00"))

        assert suprimento.valor_gasto == Decimal("500.00")

    def test_saldo_remanescente_property(self, suprimento_factory, despesa_factory):
        """Propriedade saldo_remanescente deve calcular corretamente."""
        suprimento = suprimento_factory(valor_liquido=Decimal("1000.00"))
        despesa_factory(suprimento=suprimento, valor=Decimal("300.00"))
        despesa_factory(suprimento=suprimento, valor=Decimal("200.00"))

        assert suprimento.saldo_remanescente == Decimal("500.00")

    def test_validacao_fim_periodo_maior_que_inicio(self, suprimento_factory):
        """Deve validar que fim_periodo >= inicio_periodo."""
        inicio = date.today()
        fim = date.today() - timedelta(days=1)

        with pytest.raises(ValidationError) as exc_info:
            suprimento_factory(inicio_periodo=inicio, fim_periodo=fim)

        assert "fim_periodo" in exc_info.value.error_dict

    def test_validacao_devolucao_maior_que_recibo(self, db, suprimento_factory):
        """Deve validar que data_devolucao >= data_recibo."""
        suprimento = suprimento_factory()
        suprimento.data_recibo = date.today()
        suprimento.data_devolucao_saldo = date.today() - timedelta(days=1)

        with pytest.raises(ValidationError) as exc_info:
            suprimento.full_clean()

        assert "data_devolucao_saldo" in exc_info.value.error_dict

    def test_str_representation(self, suprimento_factory, credor_factory):
        """__str__ deve retornar representação legível."""
        credor = credor_factory()
        suprimento = suprimento_factory(suprido=credor)
        expected = f"Suprimento: {credor.nome} - Valor: R$ 500.00"
        assert str(suprimento) == expected

    def test_sealed_queryset_bloqueia_update(self, suprimento_factory):
        """SealedMutationQuerySet.update() deve ser bloqueado."""
        suprimento_factory()

        with pytest.raises(ValidationError) as exc_info:
            SuprimentoDeFundos.objects.all().update(valor_liquido=Decimal("999.99"))

        assert "proibidas" in str(exc_info.value).lower()

    def test_sealed_queryset_bloqueia_bulk_update(self, db, suprimento_factory):
        """SealedMutationQuerySet.bulk_update() deve ser bloqueado."""
        suprimento = suprimento_factory()

        with pytest.raises(ValidationError) as exc_info:
            SuprimentoDeFundos.objects.bulk_update([suprimento], fields=["valor_liquido"])

        assert "proibidas" in str(exc_info.value).lower()

    def test_sealed_queryset_bloqueia_bulk_create(self, db, suprimento_factory):
        """SealedMutationQuerySet.bulk_create() deve ser bloqueado."""
        with pytest.raises(ValidationError) as exc_info:
            SuprimentoDeFundos.objects.bulk_create([])

        assert "proibidas" in str(exc_info.value).lower()

    def test_save_aplica_clean(self, suprimento_factory):
        """Save deve invocar full_clean()."""
        inicio = date.today()
        fim = date.today() - timedelta(days=1)

        with pytest.raises(ValidationError):
            suprimento = suprimento_factory(inicio_periodo=inicio, fim_periodo=fim)

    def test_periodo_igual_permitido(self, suprimento_factory):
        """Deve permitir fim_periodo igual a inicio_periodo."""
        data = date.today()
        suprimento = suprimento_factory(inicio_periodo=data, fim_periodo=data)
        assert suprimento.pk is not None


class TestDespesaSuprimentoModel:
    """Testes para o modelo DespesaSuprimento."""

    def test_create_despesa_basica(self, despesa_factory):
        """Despesa deve ser criada com campos obrigatórios."""
        despesa = despesa_factory()
        assert despesa.pk is not None
        assert despesa.valor == Decimal("100.00")

    def test_valor_nao_negativo(self, despesa_factory):
        """Despesa com valor negativo deve falhar na validação."""
        with pytest.raises(ValidationError) as exc_info:
            despesa = despesa_factory(valor=Decimal("-50.00"))

        assert "valor" in str(exc_info.value).lower() or "negativo" in str(exc_info.value).lower()

    def test_str_representation(self, despesa_factory):
        """__str__ deve retornar representação legível."""
        despesa = despesa_factory(
            valor=Decimal("150.00"),
            estabelecimento="Loja X",
            data=date(2026, 5, 1)
        )
        expected = "2026-05-01 - Loja X - R$ 150.00"
        assert str(despesa) == expected

    def test_sealed_queryset_bloqueia_update(self, despesa_factory):
        """DespesaSuprimento.update() deve ser bloqueado."""
        despesa_factory()

        with pytest.raises(ValidationError) as exc_info:
            DespesaSuprimento.objects.all().update(valor=Decimal("999.99"))

        assert "proibidas" in str(exc_info.value).lower()

    def test_processo_referencia_retorna_processo_suprimento(self, despesa_factory, suprimento_factory, processo_factory):
        """_processo_referencia() deve retornar o processo vinculado via suprimento."""
        processo = processo_factory()
        suprimento = suprimento_factory(processo=processo)
        despesa = despesa_factory(suprimento=suprimento)

        assert despesa._processo_referencia() == processo

    def test_processo_referencia_retorna_none_sem_suprimento(self, db):
        """_processo_referencia() deve retornar None se suprimento não existe."""
        despesa = DespesaSuprimento(
            data=date.today(),
            estabelecimento="Test",
            valor=Decimal("100.00")
        )
        assert despesa._processo_referencia() is None


class TestPrestacaoContasSuprimentoModel:
    """Testes para o modelo PrestacaoContasSuprimento."""

    def test_create_prestacao_basica(self, prestacao_contas_factory):
        """Prestação de contas deve ser criada com status padrão ABERTA."""
        prestacao = prestacao_contas_factory()
        assert prestacao.pk is not None
        assert prestacao.status == PrestacaoContasSuprimento.STATUS_ABERTA

    def test_status_choices(self):
        """Deve ter todos os status esperados."""
        assert PrestacaoContasSuprimento.STATUS_ABERTA == "ABERTA"
        assert PrestacaoContasSuprimento.STATUS_ENVIADA == "ENVIADA"
        assert PrestacaoContasSuprimento.STATUS_ENCERRADA == "ENCERRADA"

    def test_str_representation(self, prestacao_contas_factory):
        """__str__ deve retornar representação legível com status."""
        prestacao = prestacao_contas_factory(status=PrestacaoContasSuprimento.STATUS_ENVIADA)
        assert "Prestação" in str(prestacao)
        assert "ENVIADA" in str(prestacao) or "Aguardando Revisão" in str(prestacao)

    def test_one_to_one_with_suprimento(self, suprimento_factory, prestacao_contas_factory):
        """Deve ser one-to-one com SuprimentoDeFundos."""
        suprimento = suprimento_factory()
        prestacao = prestacao_contas_factory(suprimento=suprimento)

        assert suprimento.prestacao_contas == prestacao

    def test_nao_pode_atualizar_suprimento_constraint(self, prestacao_contas_factory):
        """SuprimentoDeFundos não deve poder ser deletado se tem prestação."""
        prestacao = prestacao_contas_factory()
        suprimento = prestacao.suprimento

        with pytest.raises(Exception):  # ProtectedError esperado
            suprimento.delete()


class TestModelValidations:
    """Testes para validações de modelos."""

    def test_valor_minvalue_validator_suprimento(self, suprimento_factory):
        """Suprimento com valor_liquido negativo deve falhar."""
        with pytest.raises(ValidationError):
            SuprimentoDeFundos(
                suprimento_factory().suprido,
                valor_liquido=Decimal("-100.00"),
                inicio_periodo=date.today(),
                fim_periodo=date.today() + timedelta(days=30),
                status_id=1
            ).full_clean()

    def test_taxa_saque_nao_negativa(self, suprimento_factory):
        """Taxa de saque negativa deve falhar na validação."""
        with pytest.raises(ValidationError):
            suprimento = suprimento_factory(taxa_saque=Decimal("-5.00"))


class TestModelHistory:
    """Testes para rastreamento de histórico via simple_history."""

    def test_suprimento_tem_history(self, suprimento_factory):
        """SuprimentoDeFundos deve ter histórico."""
        suprimento = suprimento_factory()
        assert hasattr(suprimento, 'history')

    def test_despesa_tem_history(self, despesa_factory):
        """DespesaSuprimento deve ter histórico."""
        despesa = despesa_factory()
        assert hasattr(despesa, 'history')

    def test_prestacao_tem_history(self, prestacao_contas_factory):
        """PrestacaoContasSuprimento deve ter histórico."""
        prestacao = prestacao_contas_factory()
        assert hasattr(prestacao, 'history')
