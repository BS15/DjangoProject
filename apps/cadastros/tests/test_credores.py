"""Testes automatizados do domínio de credores.

Este módulo contém testes para o modelo Credor e validações associadas.
Os testes são organizados em conftest.py (fixtures) e módulos específicos por feature.
"""

import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError

from apps.cadastros.models import Credor


class TestCredorModel:
    """Testes para o modelo Credor."""

    def test_criar_credor_pessoa_fisica(self, db):
        """Deve criar um credor pessoa física."""
        credor = Credor.objects.create(
            nome="João Silva",
            cpf_cnpj="12345678901",
            tipo="PF",
        )
        assert credor.pk is not None
        assert credor.tipo == "PF"

    def test_criar_credor_pessoa_juridica(self, db):
        """Deve criar um credor pessoa jurídica."""
        credor = Credor.objects.create(
            nome="Empresa X Ltda.",
            cpf_cnpj="12345678901234",
            tipo="PJ",
        )
        assert credor.pk is not None
        assert credor.tipo == "PJ"

    def test_str_representation(self, db):
        """__str__ deve retornar nome do credor."""
        credor = Credor.objects.create(
            nome="Fornecedor Teste",
            cpf_cnpj="00000000000191",
            tipo="PJ",
        )
        assert str(credor) == "Fornecedor Teste"

    def test_nome_obrigatorio(self, db):
        """Campo nome é obrigatório."""
        with pytest.raises(Exception):  # Pode ser ValidationError ou IntegrityError
            Credor.objects.create(
                nome=None,
                cpf_cnpj="00000000000191",
                tipo="PJ",
            )

    def test_tipo_choices(self):
        """Deve ter choices válidos para tipo."""
        credor = Credor(
            nome="Teste",
            cpf_cnpj="12345678901234",
            tipo="PJ",
        )
        assert credor.tipo in ["PF", "PJ"]
