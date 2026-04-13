"""Filtros de listagem para o domínio de fluxo financeiro e documental.

Este módulo define filtros para pesquisa e listagem de processos, documentos e pagamentos no fluxo financeiro.
"""

import django_filters
from fluxo.domain_models import (
	Processo,
	Pendencia,
	Contingencia,
	Devolucao,
	TiposDePagamento,
	StatusChoicesProcesso,
	STATUS_CONTINGENCIA,
)


class BaseStyledFilterSet(django_filters.FilterSet):
	"""Base de filtros com estilo Bootstrap consistente."""

	def __init__(self, *args, **kwargs):
		"""Aplica classes Bootstrap em todos os campos do formulário de filtro."""
		super().__init__(*args, **kwargs)
		for field in self.form.fields.values():
			field.widget.attrs.update({'class': 'form-control form-control-sm'})


class ProcessoFilter(BaseStyledFilterSet):
	"""Filtro completo para listagem de processos de pagamento."""

	credor_nome = django_filters.CharFilter(field_name='credor__nome', lookup_expr='icontains', label='Credor (Nome)')
	n_nota_empenho = django_filters.CharFilter(method='filter_n_nota_empenho', label='Nº Empenho')
	ano_exercicio = django_filters.NumberFilter(method='filter_ano_exercicio', label='Ano Exercício')

	data_empenho = django_filters.DateFromToRangeFilter(method='filter_data_empenho', label='Data Empenho (De - Até)', widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))
	data_vencimento = django_filters.DateFromToRangeFilter(label='Data Vencimento (De - Até)', widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))
	data_pagamento = django_filters.DateFromToRangeFilter(label='Data Pagamento (De - Até)', widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))

	valor_bruto = django_filters.RangeFilter(label='Valor Bruto (Min - Max)')
	valor_liquido = django_filters.RangeFilter(label='Valor Líquido (Min - Max)')

	class Meta:
		model = Processo
		fields = [
			'n_nota_empenho', 'n_pagamento_siscac', 'observacao', 'detalhamento',
			'extraorcamentario', 'forma_pagamento', 'tipo_pagamento', 'status', 'tag', 'conta',
			'data_empenho', 'data_vencimento', 'data_pagamento', 'valor_bruto', 'valor_liquido'
		]

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
	processo__credor__nome = django_filters.CharFilter(lookup_expr='icontains', label="Credor")

	class Meta:
		model = Pendencia
		fields = ['status', 'tipo', 'processo__id', 'processo__credor__nome']


class DevolucaoFilter(BaseStyledFilterSet):
	"""Filtro para devoluções com critérios por período, processo e credor."""

	processo__id = django_filters.NumberFilter(label="Nº do Processo")
	processo__credor__nome = django_filters.CharFilter(lookup_expr='icontains', label="Credor")
	data_devolucao__gte = django_filters.DateFilter(
		field_name='data_devolucao', lookup_expr='gte', label='Data Devolução (de)'
	)
	data_devolucao__lte = django_filters.DateFilter(
		field_name='data_devolucao', lookup_expr='lte', label='Data Devolução (até)'
	)
	motivo = django_filters.CharFilter(lookup_expr='icontains', label='Motivo')

	class Meta:
		model = Devolucao
		fields = ['processo__id', 'processo__credor__nome', 'data_devolucao__gte', 'data_devolucao__lte', 'motivo']

	def __init__(self, *args, **kwargs):
		"""Inicializa filtros de devolução com widgets de data no formato nativo."""
		super().__init__(*args, **kwargs)
		self.form.fields['data_devolucao__gte'].widget.attrs['type'] = 'date'
		self.form.fields['data_devolucao__lte'].widget.attrs['type'] = 'date'


class ContingenciaFilter(BaseStyledFilterSet):
	"""Filtro para acompanhamento de solicitações de contingência."""

	processo__id = django_filters.NumberFilter(label="Nº do Processo")
	solicitante__username = django_filters.CharFilter(lookup_expr='icontains', label="Solicitante")
	status = django_filters.ChoiceFilter(choices=STATUS_CONTINGENCIA, label="Status", empty_label="Todos os Status")

	class Meta:
		model = Contingencia
		fields = ['processo__id', 'solicitante__username', 'status']


class AEmpenharFilter(ProcessoFilter):
	"""Filtro enxuto da fila `A EMPENHAR`, reaproveitando `ProcessoFilter`."""

	tipo_pagamento = django_filters.ModelChoiceFilter(
		queryset=TiposDePagamento.objects.filter(is_active=True),
		label='Tipo de Pagamento',
		empty_label='Todos',
	)
	data_vencimento__gte = django_filters.DateFilter(
		field_name='data_vencimento', lookup_expr='gte', label='Vencimento De'
	)
	data_vencimento__lte = django_filters.DateFilter(
		field_name='data_vencimento', lookup_expr='lte', label='Vencimento Até'
	)

	class Meta(ProcessoFilter.Meta):
		fields = ['credor_nome', 'tipo_pagamento', 'data_vencimento__gte', 'data_vencimento__lte', 'valor_liquido']

	def __init__(self, *args, **kwargs):
		"""Configura campos de vencimento com input nativo de data."""
		super().__init__(*args, **kwargs)
		self.form.fields['data_vencimento__gte'].widget.input_type = 'date'
		self.form.fields['data_vencimento__lte'].widget.input_type = 'date'

