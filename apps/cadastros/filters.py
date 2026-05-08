"""Filtros de listagem para o domínio de credores."""

from apps.pagamentos.filters import BaseStyledFilterSet, icontains_filter
from apps.cadastros.models import Credor


class CredorFilter(BaseStyledFilterSet):
    """Filtro para pesquisa de credores por dados cadastrais principais."""

    nome = icontains_filter(label='Nome')
    cpf_cnpj = icontains_filter(label='CPF/CNPJ')

    class Meta:
        model = Credor
        fields = ['tipo', 'ativo']
