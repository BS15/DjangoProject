import django_filters
from .models import Processo, Credor, Diaria, ReembolsoCombustivel, Jeton, AuxilioRepresentacao, RetencaoImposto, CodigosImposto, DocumentoFiscal, StatusChoicesRetencoes, StatusChoicesVerbasIndenizatorias, StatusChoicesPendencias, StatusChoicesProcesso, Pendencia, Contingencia, STATUS_CONTINGENCIA, Devolucao, TiposDePagamento


class BaseStyledFilterSet(django_filters.FilterSet):
    """Base de filtros com estilo Bootstrap consistente."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.form.fields.values():
            field.widget.attrs.update({'class': 'form-control form-control-sm'})


class ProcessoFilter(BaseStyledFilterSet):
    credor_nome = django_filters.CharFilter(field_name='credor__nome', lookup_expr='icontains', label='Credor (Nome)')
    n_nota_empenho = django_filters.CharFilter(lookup_expr='icontains', label='Nº Empenho')

    # Date Ranges
    data_empenho = django_filters.DateFromToRangeFilter(label='Data Empenho (De - Até)', widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))
    data_vencimento = django_filters.DateFromToRangeFilter(label='Data Vencimento (De - Até)', widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))
    data_pagamento = django_filters.DateFromToRangeFilter(label='Data Pagamento (De - Até)', widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}))

    # Value Ranges
    valor_bruto = django_filters.RangeFilter(label='Valor Bruto (Min - Max)')
    valor_liquido = django_filters.RangeFilter(label='Valor Líquido (Min - Max)')

    class Meta:
        model = Processo
        fields = [
            'n_nota_empenho', 'n_pagamento_siscac', 'observacao', 'detalhamento',
            'extraorcamentario', 'ano_exercicio', 'forma_pagamento', 'tipo_pagamento', 'status', 'tag', 'conta',
            'data_empenho', 'data_vencimento', 'data_pagamento', 'valor_bruto', 'valor_liquido'
        ]


class CredorFilter(BaseStyledFilterSet):
    class Meta:
        model = Credor
        fields = {
            'nome': ['icontains'],       # Busca parcial ignorando maiúsculas
            'cpf_cnpj': ['icontains'],   # Busca parcial
            'tipo': ['exact'],           # Dropdown exato (PF, PJ, EX)
            'cargo_funcao': ['exact'],   # Dropdown por cargo/função
        }

# Filtro para Diárias
class DiariaFilter(BaseStyledFilterSet):
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

# Filtro para Reembolso
class ReembolsoFilter(BaseStyledFilterSet):
    class Meta:
        model = ReembolsoCombustivel
        fields = {
            'numero_sequencial': ['icontains'],
            'beneficiario': ['exact'],
            'status': ['exact'],
        }
# Filtro para Jeton
class JetonFilter(BaseStyledFilterSet):
    class Meta:
        model = Jeton
        fields = {
            'numero_sequencial': ['icontains'],
            'beneficiario': ['exact'],
            'reuniao': ['icontains'],
            'status': ['exact'],
        }
# Filtro para Auxílio Representação
class AuxilioFilter(BaseStyledFilterSet):
    class Meta:
        model = AuxilioRepresentacao
        fields = {
            'numero_sequencial': ['icontains'],
            'beneficiario': ['exact'],
            'status': ['exact'],
        }

class RetencaoNotaFilter(BaseStyledFilterSet):
    """ Filtro para quando a visão for 'Agrupar por Nota Fiscal' """
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
        fields = ['mes', 'ano', 'processo', 'emitente', 'beneficiario', 'imposto', 'status']  # <-- Adicione aqui


class RetencaoProcessoFilter(BaseStyledFilterSet):
    """ Filtro para quando a visão for 'Agrupar por Processo' """
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
    """ Filtro para a visão granular (Listar Impostos Individuais) """
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


class PendenciaFilter(BaseStyledFilterSet):
    processo__id = django_filters.NumberFilter(label="ID do Processo")
    # Permite buscar pelo nome do credor do processo atrelado à pendência
    processo__credor__nome = django_filters.CharFilter(lookup_expr='icontains', label="Credor")

    class Meta:
        model = Pendencia
        fields = ['status', 'tipo', 'processo__id', 'processo__credor__nome']

class DocumentoFiscalFilter(BaseStyledFilterSet):
    numero_nota_fiscal = django_filters.CharFilter(lookup_expr='icontains', label='Nº da Nota')
    # Permite buscar parte do nome do credor
    nome_emitente__nome = django_filters.CharFilter(lookup_expr='icontains', label='Nome do Emitente')

    # Filtro para o campo booleano (Atestada = Sim/Não/Qualquer)
    atestada = django_filters.BooleanFilter(
        label='Status de Liquidação (Atestada?)',
        widget=django_filters.widgets.BooleanWidget()
    )

    class Meta:
        model = DocumentoFiscal
        fields = ['numero_nota_fiscal', 'nome_emitente__nome', 'atestada']

class DevolucaoFilter(BaseStyledFilterSet):
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
        super().__init__(*args, **kwargs)
        self.form.fields['data_devolucao__gte'].widget.attrs['type'] = 'date'
        self.form.fields['data_devolucao__lte'].widget.attrs['type'] = 'date'


class ContingenciaFilter(BaseStyledFilterSet):
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
        super().__init__(*args, **kwargs)
        self.form.fields['data_vencimento__gte'].widget.input_type = 'date'
        self.form.fields['data_vencimento__lte'].widget.input_type = 'date'
