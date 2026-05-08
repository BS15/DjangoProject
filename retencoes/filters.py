"""Filtros de listagem para o domínio fiscal (retenções e documentos fiscais)."""

import django_filters
from apps.pagamentos.filters import (
    BaseStyledFilterSet,
    boolean_filter,
    exact_text_filter,
    icontains_filter,
    month_filter,
    year_filter,
)
from cadastros.models import Credor
from retencoes.models import DocumentoFiscal, RetencaoImposto, CodigosImposto, StatusChoicesRetencoes
from apps.pagamentos.domain_models import Processo


class RetencaoNotaFilter(BaseStyledFilterSet):
    """Filtro de retenções na visão agrupada por documento fiscal."""

    mes = month_filter('data_emissao', label='Mês da Emissão')
    ano = year_filter('data_emissao', label='Ano da Emissão')
    processo = exact_text_filter(field_name='processo__id', label='Nº do Processo')
    emitente = icontains_filter(field_name='nome_emitente', label='Emitente/Credor')
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

    mes = month_filter('notas_fiscais__data_emissao', label='Mês da Emissão')
    ano = year_filter('notas_fiscais__data_emissao', label='Ano da Emissão')
    processo = exact_text_filter(field_name='id', label='Nº do Processo')
    credor = icontains_filter(field_name='credor__nome', label='Credor')
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

    mes = month_filter('nota_fiscal__data_emissao', label='Mês (Emissão NF)')
    ano = year_filter('nota_fiscal__data_emissao', label='Ano (Emissão NF)')
    nota_fiscal = icontains_filter(field_name='nota_fiscal__numero_nota_fiscal', label='Nº Documento Fiscal')
    processo_lancamento = exact_text_filter(field_name='nota_fiscal__processo__id', label='Processo de Lançamento')
    emitente = exact_text_filter(field_name='nota_fiscal__nome_emitente', label='Emitente/Credor')
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
        fields = ['mes', 'ano', 'nota_fiscal', 'processo_lancamento', 'emitente', 'beneficiario', 'imposto', 'status']


class DocumentoFiscalFilter(BaseStyledFilterSet):
    """Filtro para documentos fiscais por número, emitente e ateste."""

    numero_nota_fiscal = icontains_filter(label='Nº da Nota')
    nome_emitente__nome = icontains_filter(label='Nome do Emitente')
    atestada = boolean_filter(label='Status de Liquidação (Atestada?)')

    class Meta:
        model = DocumentoFiscal
        fields = ['numero_nota_fiscal', 'nome_emitente__nome', 'atestada']
