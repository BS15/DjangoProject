"""Filtros de listagem para o domínio de credores."""

import django_filters
from pagamentos.filters import BaseStyledFilterSet
from credores.models import Credor


class CredorFilter(BaseStyledFilterSet):
    """Filtro para pesquisa de credores por dados cadastrais principais."""

    class Meta:
        model = Credor
        fields = '__all__'
