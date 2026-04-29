"""Filtros de listagem para o domínio de verbas indenizatórias."""

import django_filters
from pagamentos.filters import BaseStyledFilterSet
from verbas_indenizatorias.models import (
    Diaria,
    ReembolsoCombustivel,
    Jeton,
    AuxilioRepresentacao,
    Tabela_Valores_Unitarios_Verbas_Indenizatorias,
)


class DiariaFilter(BaseStyledFilterSet):
    """Filtro para listagem de diárias com critérios operacionais."""

    data_saida = django_filters.DateFromToRangeFilter(label='Data Saída (De - Até)', widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))
    beneficiario__nome = django_filters.CharFilter(lookup_expr='icontains', label='Nome do Beneficiário')
    proponente__username = django_filters.CharFilter(lookup_expr='icontains', label='Username do Proponente')
    autorizada = django_filters.BooleanFilter(label='Status de Autorização (Autorizada?)', widget=django_filters.widgets.BooleanWidget())

    class Meta:
        model = Diaria
        fields = '__all__'


class ReembolsoFilter(BaseStyledFilterSet):
    """Filtro para reembolsos de combustível."""

    class Meta:
        model = ReembolsoCombustivel
        fields = '__all__'


class JetonFilter(BaseStyledFilterSet):
    """Filtro para lançamentos de jeton."""

    class Meta:
        model = Jeton
        fields = '__all__'


class AuxilioFilter(BaseStyledFilterSet):
    """Filtro para auxílios de representação."""

    class Meta:
        model = AuxilioRepresentacao
        fields = '__all__'


class TabelaValoresUnitariosFilter(BaseStyledFilterSet):
    """Filtro para tabela de valores unitários de verbas."""

    class Meta:
        model = Tabela_Valores_Unitarios_Verbas_Indenizatorias
        fields = '__all__'
