"""Filtros de listagem para o domínio de credores."""

import django_filters
from fluxo.filters import BaseStyledFilterSet
from credores.models import Credor


class CredorFilter(BaseStyledFilterSet):
    """Filtro para pesquisa de credores por dados cadastrais principais."""

    class Meta:
        model = Credor
        fields = {
            'nome': ['icontains'],
            'cpf_cnpj': ['icontains'],
            'tipo': ['exact'],
            'cargo_funcao': ['exact'],
        }
