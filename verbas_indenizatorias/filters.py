"""Filtros de listagem para o domínio de verbas indenizatórias."""

import django_filters
from fluxo.filters import BaseStyledFilterSet
from verbas_indenizatorias.models import Diaria, ReembolsoCombustivel, Jeton, AuxilioRepresentacao


class DiariaFilter(BaseStyledFilterSet):
    """Filtro para listagem de diárias com critérios operacionais."""

    data_saida = django_filters.DateFromToRangeFilter(label='Data Saída (De - Até)', widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))
    beneficiario__nome = django_filters.CharFilter(lookup_expr='icontains', label='Nome do Beneficiário')
    proponente__username = django_filters.CharFilter(lookup_expr='icontains', label='Username do Proponente')
    autorizada = django_filters.BooleanFilter(label='Status de Autorização (Autorizada?)', widget=django_filters.widgets.BooleanWidget())

    class Meta:
        model = Diaria
        fields = [
            'numero_siscac', 'beneficiario', 'proponente',
            'status', 'cidade_destino',
        ]


class ReembolsoFilter(BaseStyledFilterSet):
    """Filtro para reembolsos de combustível."""

    class Meta:
        model = ReembolsoCombustivel
        fields = {
            'numero_sequencial': ['icontains'],
            'beneficiario': ['exact'],
            'status': ['exact'],
        }


class JetonFilter(BaseStyledFilterSet):
    """Filtro para lançamentos de jeton."""

    class Meta:
        model = Jeton
        fields = {
            'numero_sequencial': ['icontains'],
            'beneficiario': ['exact'],
            'reuniao': ['icontains'],
            'status': ['exact'],
        }


class AuxilioFilter(BaseStyledFilterSet):
    """Filtro para auxílios de representação."""

    class Meta:
        model = AuxilioRepresentacao
        fields = {
            'numero_sequencial': ['icontains'],
            'beneficiario': ['exact'],
            'status': ['exact'],
        }
