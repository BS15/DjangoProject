"""Filtros de listagem para o domínio fiscal (retenções e documentos fiscais)."""

import django_filters
from pagamentos.filters import BaseStyledFilterSet
from credores.models import Credor
from fiscal.models import DocumentoFiscal, RetencaoImposto, CodigosImposto, StatusChoicesRetencoes
from pagamentos.domain_models import Processo


class RetencaoNotaFilter(BaseStyledFilterSet):
    """Filtro de retenções na visão agrupada por documento fiscal."""

    mes = django_filters.NumberFilter(field_name='data_emissao', lookup_expr='month', label='Mês da Emissão')
    ano = django_filters.NumberFilter(field_name='data_emissao', lookup_expr='year', label='Ano da Emissão')
    processo = django_filters.CharFilter(field_name='processo__id', lookup_expr='exact', label='Nº do Processo')
    emitente = django_filters.CharFilter(field_name='nome_emitente', lookup_expr='icontains', label='Emitente/Credor')
    beneficiario = django_filters.ModelChoiceFilter(
        field_name='retencoes__beneficiario',
        queryset=Credor.objects.all(),
        label='Beneficiário'
    )
    imposto = django_filters.ModelChoiceFilter(
        field_name='retencoes__codigo',
        queryset=CodigosImposto.objects.filter(is_active=True),
        label='Tipo de Imposto'
    )
    status = django_filters.ModelChoiceFilter(
        field_name='retencoes__status',
        queryset=StatusChoicesRetencoes.objects.filter(is_active=True),
        label='Status'
    )

    class Meta:
        model = DocumentoFiscal
        fields = ['mes', 'ano', 'processo', 'emitente', 'beneficiario', 'imposto', 'status']


class RetencaoProcessoFilter(BaseStyledFilterSet):
    """Filtro de retenções na visão agrupada por processo."""

    mes = django_filters.NumberFilter(field_name='notas_fiscais__data_emissao', lookup_expr='month', label='Mês da Emissão')
    ano = django_filters.NumberFilter(field_name='notas_fiscais__data_emissao', lookup_expr='year', label='Ano da Emissão')
    processo = django_filters.CharFilter(field_name='id', lookup_expr='exact', label='Nº do Processo')
    credor = django_filters.CharFilter(field_name='credor__nome', lookup_expr='icontains', label='Credor')
    imposto = django_filters.ModelChoiceFilter(
        field_name='notas_fiscais__retencoes__codigo',
        queryset=CodigosImposto.objects.filter(is_active=True),
        label='Tipo de Imposto'
    )
    status = django_filters.ModelChoiceFilter(
        field_name='notas_fiscais__retencoes__status',
        queryset=StatusChoicesRetencoes.objects.filter(is_active=True),
        label='Status'
    )

    class Meta:
        model = Processo
        fields = ['mes', 'ano', 'processo', 'credor', 'imposto', 'status']


class RetencaoIndividualFilter(BaseStyledFilterSet):
    """Filtro granular para listagem individual de impostos retidos."""

    mes = django_filters.NumberFilter(field_name='nota_fiscal__data_emissao', lookup_expr='month', label='Mês (Emissão NF)')
    ano = django_filters.NumberFilter(field_name='nota_fiscal__data_emissao', lookup_expr='year', label='Ano (Emissão NF)')
    processo = django_filters.CharFilter(field_name='nota_fiscal__processo__id', lookup_expr='exact', label='Nº do Processo')
    emitente = django_filters.CharFilter(field_name='nota_fiscal__nome_emitente', lookup_expr='exact', label='Emitente/Credor')
    beneficiario = django_filters.ModelChoiceFilter(
        field_name='beneficiario',
        queryset=Credor.objects.all(),
        label='Beneficiário'
    )
    imposto = django_filters.ModelChoiceFilter(
        field_name='codigo',
        queryset=CodigosImposto.objects.filter(is_active=True),
        label='Tipo de Imposto'
    )
    status = django_filters.ModelChoiceFilter(
        field_name='status',
        queryset=StatusChoicesRetencoes.objects.filter(is_active=True),
        label='Status'
    )

    class Meta:
        model = RetencaoImposto
        fields = ['mes', 'ano', 'processo', 'emitente', 'beneficiario', 'imposto', 'status']


class DocumentoFiscalFilter(BaseStyledFilterSet):
    """Filtro para documentos fiscais por número, emitente e ateste."""

    numero_nota_fiscal = django_filters.CharFilter(lookup_expr='icontains', label='Nº da Nota')
    nome_emitente__nome = django_filters.CharFilter(lookup_expr='icontains', label='Nome do Emitente')
    atestada = django_filters.BooleanFilter(
        label='Status de Liquidação (Atestada?)',
        widget=django_filters.widgets.BooleanWidget()
    )

    class Meta:
        model = DocumentoFiscal
        fields = ['numero_nota_fiscal', 'nome_emitente__nome', 'atestada']
