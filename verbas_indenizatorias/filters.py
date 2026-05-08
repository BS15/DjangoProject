"""Filtros de listagem para o domínio de verbas indenizatórias."""

import django_filters
from pagamentos.filters import BaseStyledFilterSet, date_range_filter, icontains_filter
from verbas_indenizatorias.models import (
    Diaria,
    ReembolsoCombustivel,
    Jeton,
    AuxilioRepresentacao,
    Tabela_Valores_Unitarios_Verbas_Indenizatorias,
)


class DiariaFilter(BaseStyledFilterSet):
    """Filtro para listagem de diárias com critérios operacionais."""

    numero_siscac__icontains = icontains_filter(field_name='numero_siscac', label='Nº SISCAC')
    data_saida = date_range_filter(label='Data Saída (De - Até)')
    cidade_destino__icontains = icontains_filter(field_name='cidade_destino', label='Destino')

    class Meta:
        model = Diaria
        fields = ['beneficiario', 'status']


class ReembolsoFilter(BaseStyledFilterSet):
    """Filtro para reembolsos de combustível."""

    numero_sequencial__icontains = icontains_filter(field_name='numero_sequencial', label='Nº Seq.')

    class Meta:
        model = ReembolsoCombustivel
        fields = ['beneficiario', 'status']


class JetonFilter(BaseStyledFilterSet):
    """Filtro para lançamentos de jeton."""

    numero_sequencial__icontains = icontains_filter(field_name='numero_sequencial', label='Nº Seq.')
    reuniao__icontains = icontains_filter(field_name='reuniao', label='Reunião')

    class Meta:
        model = Jeton
        fields = ['beneficiario', 'status']


class AuxilioFilter(BaseStyledFilterSet):
    """Filtro para auxílios de representação."""

    numero_sequencial__icontains = icontains_filter(field_name='numero_sequencial', label='N Seq.')

    class Meta:
        model = AuxilioRepresentacao
        fields = ['beneficiario', 'status']


class TabelaValoresUnitariosFilter(BaseStyledFilterSet):
    """Filtro para tabela de valores unitários de verbas."""

    class Meta:
        model = Tabela_Valores_Unitarios_Verbas_Indenizatorias
        fields = '__all__'
