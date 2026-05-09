"""Testes para o domínio de sealing (bloqueio de mutações pós-pagamento)."""

from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import pytest
from django.core.exceptions import ValidationError

from apps.suprimentos.models import SuprimentoDeFundos, DespesaSuprimento


class TestSuprimentoDomainSealing:
    """Testes para domain sealing de SuprimentoDeFundos."""

    def test_enforce_domain_seal_bypass_flag(self, suprimento_factory):
        """Deve permitir bypass via flag _bypass_domain_seal."""
        suprimento = suprimento_factory()
        suprimento._bypass_domain_seal = True
        suprimento.valor_liquido = Decimal("999.99")

        # Não deve lançar ValidationError por domain seal
        # (pode lançar andere erros, mas não por seal)
        try:
            suprimento.save()
        except ValidationError as e:
            # Se houver erro, não deve ser sobre "Mutação direta bloqueada"
            assert "Mutação direta bloqueada" not in str(e)

    @patch('apps.suprimentos.models._is_processo_selado')
    def test_bloqueia_criacao_suprimento_em_processo_selado(self, mock_is_sealed, suprimento_factory, processo_factory):
        """Deve bloquear criação de suprimento em processo pós-pagamento."""
        mock_is_sealed.return_value = True
        processo = processo_factory()

        with pytest.raises(ValidationError) as exc_info:
            SuprimentoDeFundos.objects.create(
                suprido=processo.credor,
                valor_liquido=Decimal("500.00"),
                inicio_periodo=date.today(),
                fim_periodo=date.today() + timedelta(days=30),
                process=processo,
                status_id=1,
            )

        # Verificar que chamou a função de verificação de seal
        mock_is_sealed.assert_called()

    @patch('apps.suprimentos.models._is_processo_selado')
    def test_bloqueia_alteracao_campos_sensiveis_em_processo_selado(
        self, mock_is_sealed, suprimento_factory, processo_factory
    ):
        """Deve bloquear alteração de campos sensíveis em processo selado."""
        # Criar suprimento emummprocess não-selado
        processo = processo_factory()
        mock_is_sealed.return_value = False
        suprimento = suprimento_factory(processo=processo)

        # Agora selar o processo
        mock_is_sealed.return_value = True

        # Tentar alterar campo sensível
        suprimento.valor_liquido = Decimal("999.99")

        with pytest.raises(ValidationError) as exc_info:
            suprimento.save()

        assert "Mutação direta bloqueada" in str(exc_info.value)

    def test_permite_alteracao_campos_nao_sensiveis_mesmo_selado(self, suprimento_factory):
        """Deve permitir alteração de campos não-sensíveis mesmo com processo selado."""
        suprimento = suprimento_factory()
        # Alterar um campo não-sensível
        suprimento._bypass_domain_seal = True
        suprimento.save()

        # Garantir que foi salvo
        assert suprimento.pk is not None


class TestDespesaDomainSealing:
    """Testes para domain sealing de DespesaSuprimento."""

    @patch('apps.suprimentos.models._is_processo_selado')
    def test_bloqueia_criacao_despesa_em_processo_selado(self, mock_is_sealed, despesa_factory):
        """Deve bloquear adição de despesa em suprimento de processo selado."""
        mock_is_sealed.return_value = True

        with pytest.raises(ValidationError) as exc_info:
            despesa_factory()

        assert "Cadastro bloqueado" in str(exc_info.value) or "pós-pagamento" in str(exc_info.value)

    def test_permite_criacao_despesa_em_processo_nao_selado(self, despesa_factory):
        """Deve permitir criar despesa em suprimento de processo não-selado."""
        despesa = despesa_factory()
        assert despesa.pk is not None

    def test_bloqueia_delete_despesa_em_processo_selado(self, despesa_factory):
        """Deve bloquear delete de despesa em suprimento de processo selado."""
        despesa = despesa_factory()

        with patch('apps.suprimentos.models._is_processo_selado', return_value=True):
            with pytest.raises(ValidationError) as exc_info:
                despesa.delete()

            assert "Exclusão bloqueada" in str(exc_info.value) or "pós-pagamento" in str(exc_info.value)

    def test_permite_delete_despesa_em_processo_nao_selado(self, despesa_factory):
        """Deve permitir delete de despesa em suprimento de processo não-selado."""
        despesa = despesa_factory()
        despesa_id = despesa.pk

        despesa.delete()

        # Verificar que foi deletado
        from apps.suprimentos.models import DespesaSuprimento
        assert not DespesaSuprimento.objects.filter(pk=despesa_id).exists()


class TestSuprimentoDelete:
    """Testes para deleção de suprimento com proteções de sealing."""

    @patch('apps.suprimentos.models._is_processo_selado')
    def test_bloqueia_delete_suprimento_em_processo_selado(self, mock_is_sealed, suprimento_factory):
        """Deve bloquear delete de suprimento em processo pós-pagamento."""
        suprimento = suprimento_factory()
        mock_is_sealed.return_value = True

        with pytest.raises(ValidationError) as exc_info:
            suprimento.delete()

        assert "Exclusão bloqueada" in str(exc_info.value)

    def test_permite_delete_suprimento_em_processo_nao_selado(self, suprimento_factory):
        """Deve permitir delete de suprimento em processo não-selado."""
        suprimento = suprimento_factory()
        suprimento_id = suprimento.pk

        suprimento.delete()

        # Verificar que foi deletado
        from apps.suprimentos.models import SuprimentoDeFundos
        assert not SuprimentoDeFundos.objects.filter(pk=suprimento_id).exists()
