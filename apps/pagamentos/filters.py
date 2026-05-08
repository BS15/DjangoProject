"""Filtros de listagem para o domínio de fluxo financeiro e documental.

Este módulo define filtros para pesquisa e listagem de processos, documentos e pagamentos no fluxo financeiro.
"""

import django_filters
from django.db import models
from apps.pagamentos.models import (
	Processo,
	Pendencia,
	Contingencia,
	Devolucao,
	TiposDePagamento,
	StatusChoicesProcesso,
	STATUS_CONTINGENCIA,
)


def date_range_filter(*, label, method=None):
	"""Cria um filtro de intervalo de datas com widget HTML nativo."""
	return django_filters.DateFromToRangeFilter(
		label=label,
		method=method,
		widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}),
	)


def month_filter(field_name, *, label='Mês'):
	"""Cria um filtro numérico para mês a partir de um campo de data."""
	return django_filters.NumberFilter(field_name=field_name, lookup_expr='month', label=label)


def year_filter(field_name, *, label='Ano'):
	"""Cria um filtro numérico para ano a partir de um campo de data."""
	return django_filters.NumberFilter(field_name=field_name, lookup_expr='year', label=label)


def icontains_filter(*, field_name=None, label=None):
	"""Cria um filtro textual padronizado com busca parcial case-insensitive."""
	return django_filters.CharFilter(field_name=field_name, lookup_expr='icontains', label=label)


def exact_text_filter(*, field_name=None, label=None):
	"""Cria um filtro textual padronizado com comparação exata."""
	return django_filters.CharFilter(field_name=field_name, lookup_expr='exact', label=label)


def boolean_filter(*, label):
	"""Cria um filtro booleano com widget textual padronizado do django-filters."""
	return django_filters.BooleanFilter(label=label, widget=django_filters.widgets.BooleanWidget())

class BaseStyledFilterSet(django_filters.FilterSet):
	"""Base de filtros com estilo Bootstrap consistente."""

	UNSUPPORTED_TEXTUAL_FIELDS = (models.FileField, models.JSONField)

	@classmethod
	def filter_for_field(cls, field, field_name, lookup_expr=None):
		"""Converte tipos não suportados, como `FileField`, em filtros textuais."""
		if isinstance(field, cls.UNSUPPORTED_TEXTUAL_FIELDS):
			return django_filters.CharFilter(
				field_name=field_name,
				lookup_expr=lookup_expr or 'icontains',
			)
		try:
			return super().filter_for_field(field, field_name, lookup_expr)
		except AssertionError:
			return django_filters.CharFilter(
				field_name=field_name,
				lookup_expr='icontains',
			)

	def __init__(self, *args, **kwargs):
		"""Aplica classes Bootstrap em todos os campos do formulário de filtro."""
		super().__init__(*args, **kwargs)
		for field in self.form.fields.values():
			field.widget.attrs.update({'class': 'form-control form-control-sm'})


class ProcessoFilter(BaseStyledFilterSet):
	"""Filtro completo para listagem de processos de pagamento."""

	credor_nome = icontains_filter(field_name='credor__nome', label='Credor (Nome)')
	n_nota_empenho = django_filters.CharFilter(method='filter_n_nota_empenho', label='Nº Empenho')
	ano_exercicio = django_filters.NumberFilter(method='filter_ano_exercicio', label='Ano Exercício')

	data_empenho = date_range_filter(method='filter_data_empenho', label='Data Empenho (De - Até)')
	data_vencimento = date_range_filter(label='Data Vencimento (De - Até)')
	data_pagamento = date_range_filter(label='Data Pagamento (De - Até)')

	valor_bruto = django_filters.RangeFilter(label='Valor Bruto (Min - Max)')
	valor_liquido = django_filters.RangeFilter(label='Valor Líquido (Min - Max)')

	class Meta:
		model = Processo
		fields = '__all__'

	def filter_n_nota_empenho(self, queryset, name, value):
		return queryset.filter(documentos_orcamentarios__numero_nota_empenho__icontains=value).distinct()

	def filter_ano_exercicio(self, queryset, name, value):
		return queryset.filter(documentos_orcamentarios__ano_exercicio=value).distinct()

	def filter_data_empenho(self, queryset, name, value):
		if not value:
			return queryset
		if value.start:
			queryset = queryset.filter(documentos_orcamentarios__data_empenho__gte=value.start)
		if value.stop:
			queryset = queryset.filter(documentos_orcamentarios__data_empenho__lte=value.stop)
		return queryset.distinct()


class PendenciaFilter(BaseStyledFilterSet):
	"""Filtro de pendências por processo, credor e classificação."""

	processo__id = django_filters.NumberFilter(label="ID do Processo")
	processo__credor__nome = icontains_filter(label="Credor")

	class Meta:
		model = Pendencia
		fields = ['tipo', 'status']


class DevolucaoFilter(BaseStyledFilterSet):
	"""Filtro para devoluções com critérios por período, processo e credor."""

	processo__id = django_filters.NumberFilter(label="Nº do Processo")
	processo__credor__nome = icontains_filter(label="Credor")
	data_devolucao__gte = django_filters.DateFilter(
		field_name='data_devolucao', lookup_expr='gte', label='Data Devolução (de)'
	)
	data_devolucao__lte = django_filters.DateFilter(
		field_name='data_devolucao', lookup_expr='lte', label='Data Devolução (até)'
	)
	motivo = icontains_filter(label='Motivo')

	class Meta:
		model = Devolucao
		fields = []

	def __init__(self, *args, **kwargs):
		"""Inicializa filtros de devolução com widgets de data no formato nativo."""
		super().__init__(*args, **kwargs)
		self.form.fields['data_devolucao__gte'].widget.attrs['type'] = 'date'
		self.form.fields['data_devolucao__lte'].widget.attrs['type'] = 'date'


class ContingenciaFilter(BaseStyledFilterSet):
	"""Filtro para acompanhamento de solicitações de contingência."""

	processo__id = django_filters.NumberFilter(label="Nº do Processo")
	solicitante__username = icontains_filter(label="Solicitante")
	status = django_filters.ChoiceFilter(choices=STATUS_CONTINGENCIA, label="Status", empty_label="Todos os Status")

	class Meta:
		model = Contingencia
		fields = ['data_solicitacao']


class ArquivamentoFilter(BaseStyledFilterSet):
	"""Filtro enxuto do arquivo morto/digital com critérios operacionais."""

	credor_nome = icontains_filter(field_name='credor__nome', label='Credor (Nome)')
	n_nota_empenho = django_filters.CharFilter(method='filter_n_nota_empenho', label='Nº Empenho')
	data_pagamento = date_range_filter(label='Data Pagamento (De - Até)')
	valor_liquido = django_filters.RangeFilter(label='Valor Líquido (Min - Max)')

	class Meta:
		model = Processo
		fields = []

	def filter_n_nota_empenho(self, queryset, name, value):
		return queryset.filter(documentos_orcamentarios__numero_nota_empenho__icontains=value).distinct()


class AEmpenharFilter(ProcessoFilter):
	"""Filtro enxuto da fila `A EMPENHAR`, reaproveitando `ProcessoFilter`."""

	tipo_pagamento = django_filters.ModelChoiceFilter(
		queryset=TiposDePagamento.objects.filter(ativo=True),
		label='Tipo de Pagamento',
		empty_label='Todos',
	)

	class Meta(ProcessoFilter.Meta):
		# Evita herdar filtros automáticos de todos os campos do modelo (incluindo
		# campos não aderentes à fila, como arquivos) e mantém apenas filtros
		# explicitamente declarados no filtro-base + desta especialização.
		fields = []

