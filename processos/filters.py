import django_filters
from .models import Processo, Credor, Diaria, ReembolsoCombustivel, Jeton, AuxilioRepresentacao, RetencaoImposto, CodigosImposto, DocumentoFiscal, StatusChoicesRetencoes, StatusChoicesVerbasIndenizatorias, StatusChoicesPendencias, StatusChoicesProcesso, Pendencia, Contingencia, STATUS_CONTINGENCIA, Devolucao

class ProcessoFilter(django_filters.FilterSet):
    class Meta:
        model = Processo
        # Mapeamos todos os campos agrupando pelo tipo de busca desejada
        fields = {
            # Textos (Permite busca parcial ignorando maiúsculas e minúsculas)
            'n_nota_empenho': ['icontains'],
            'credor': ['exact'],
            'n_pagamento_siscac': ['icontains'],
            'observacao': ['icontains'],
            'detalhamento': ['icontains'],

            # Chaves Estrangeiras, Booleanos e Opções (Gera Dropdowns exatos)
            'extraorcamentario': ['exact'],
            'ano_exercicio': ['exact'],
            'forma_pagamento': ['exact'],
            'tipo_pagamento': ['exact'],
            'status': ['exact'],
            'tag': ['exact'],
            'conta': ['exact'],  # <-- O campo novo que criamos já entra aqui

            # Datas e Valores Numéricos
            'data_empenho': ['exact'],
            'data_vencimento': ['exact'],
            'valor_bruto': ['exact'],
            'valor_liquido': ['exact'],
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Loop para aplicar o visual do Bootstrap em todos os 17 campos gerados
        for field_name, field in self.form.fields.items():
            field.widget.attrs.update({'class': 'form-control form-control-sm'})


class CredorFilter(django_filters.FilterSet):
    class Meta:
        model = Credor
        fields = {
            'nome': ['icontains'],       # Busca parcial ignorando maiúsculas
            'cpf_cnpj': ['icontains'],   # Busca parcial
            'tipo': ['exact'],           # Dropdown exato (PF, PJ, EX)
            'grupo': ['exact'],          # Dropdown por grupo
            'cargo_funcao': ['exact'],   # Dropdown por cargo/função
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplica o visual do Bootstrap em todos os campos do filtro
        for field_name, field in self.form.fields.items():
            field.widget.attrs.update({'class': 'form-control form-control-sm'})

# Filtro para Diárias
class DiariaFilter(django_filters.FilterSet):
    class Meta:
        model = Diaria
        fields = {
            'numero_siscac': ['icontains'],
            'beneficiario': ['exact'],
            'status': ['exact'],
            'cidade_destino': ['icontains'],
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.form.fields.values():
            field.widget.attrs.update({'class': 'form-control form-control-sm'})

# Filtro para Reembolso
class ReembolsoFilter(django_filters.FilterSet):
    class Meta:
        model = ReembolsoCombustivel
        fields = {
            'numero_sequencial': ['icontains'],
            'beneficiario': ['exact'],
            'status': ['exact'],
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.form.fields.values():
            field.widget.attrs.update({'class': 'form-control form-control-sm'})

# Filtro para Jeton
class JetonFilter(django_filters.FilterSet):
    class Meta:
        model = Jeton
        fields = {
            'numero_sequencial': ['icontains'],
            'beneficiario': ['exact'],
            'reuniao': ['icontains'],
            'status': ['exact'],
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.form.fields.values():
            field.widget.attrs.update({'class': 'form-control form-control-sm'})

# Filtro para Auxílio Representação
class AuxilioFilter(django_filters.FilterSet):
    class Meta:
        model = AuxilioRepresentacao
        fields = {
            'numero_sequencial': ['icontains'],
            'beneficiario': ['exact'],
            'status': ['exact'],
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.form.fields.values():
            field.widget.attrs.update({'class': 'form-control form-control-sm'})


class RetencaoNotaFilter(django_filters.FilterSet):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.form.fields.values():
            field.widget.attrs.update({'class': 'form-control form-control-sm'})

class RetencaoProcessoFilter(django_filters.FilterSet):
    """ Filtro para quando a visão for 'Agrupar por Processo' """
    mes = django_filters.NumberFilter(field_name='notas_fiscais__data_emissao', lookup_expr='month', label='Mês da Emissão')
    ano = django_filters.NumberFilter(field_name='notas_fiscais__data_emissao', lookup_expr='year', label='Ano da Emissão')
    processo = django_filters.CharFilter(field_name='id', lookup_expr='exact', label='Nº do Processo')
    credor = django_filters.CharFilter(field_name='credor', lookup_expr='exact', label='Credor')

    imposto = django_filters.ModelChoiceFilter(
        field_name='notas_fiscais__retencoes__codigo',
        queryset=CodigosImposto.objects.filter(is_active=True),
        label='Tipo de Imposto'
    )
    status = django_filters.ModelChoiceFilter(
        field_name='retencoes__status',
        queryset=StatusChoicesRetencoes.objects.filter(is_active=True),
        label='Status'
    )

    class Meta:
        model = Processo
        fields = ['mes', 'ano', 'processo', 'credor', 'imposto', 'status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.form.fields.values():
            field.widget.attrs.update({'class': 'form-control form-control-sm'})

class RetencaoIndividualFilter(django_filters.FilterSet):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.form.fields.values():
            field.widget.attrs.update({'class': 'form-control form-control-sm'})

class PendenciaFilter(django_filters.FilterSet):
    processo__id = django_filters.NumberFilter(label="ID do Processo")
    # Permite buscar pelo nome do credor do processo atrelado à pendência
    processo__credor__nome = django_filters.CharFilter(lookup_expr='icontains', label="Credor")

    class Meta:
        model = Pendencia
        fields = ['status', 'tipo', 'processo__id', 'processo__credor__nome']

class DocumentoFiscalFilter(django_filters.FilterSet):
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

class DiariasAutorizacaoFilter(django_filters.FilterSet):
    numero_siscac = django_filters.CharFilter(lookup_expr='icontains', label='Nº SISCAC')
    beneficiario__nome = django_filters.CharFilter(lookup_expr='icontains', label='Nome do Beneficiário')
    proponente__nome = django_filters.CharFilter(lookup_expr='icontains', label='Nome do Proponente')

    autorizada = django_filters.BooleanFilter(
        label='Status de Autorização (Autorizada?)',
        widget=django_filters.widgets.BooleanWidget()
    )

    class Meta:
        model = Diaria
        fields = ['numero_siscac', 'beneficiario__nome', 'proponente__nome', 'autorizada']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.form.fields.values():
            field.widget.attrs.update({'class': 'form-control form-control-sm'})

class ArquivamentoFilter(django_filters.FilterSet):
    credor__nome = django_filters.CharFilter(lookup_expr='icontains', label='Credor')
    n_nota_empenho = django_filters.CharFilter(lookup_expr='icontains', label='Nº Empenho')
    data_pagamento__gte = django_filters.DateFilter(
        field_name='data_pagamento', lookup_expr='gte', label='Data Pagamento (de)'
    )
    data_pagamento__lte = django_filters.DateFilter(
        field_name='data_pagamento', lookup_expr='lte', label='Data Pagamento (até)'
    )
    ano_exercicio = django_filters.NumberFilter(label='Ano Exercício')

    class Meta:
        model = Processo
        fields = ['credor__nome', 'n_nota_empenho', 'data_pagamento__gte', 'data_pagamento__lte', 'ano_exercicio']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.form.fields.values():
            field.widget.attrs.update({'class': 'form-control form-control-sm'})
        self.form.fields['data_pagamento__gte'].widget.attrs['type'] = 'date'
        self.form.fields['data_pagamento__lte'].widget.attrs['type'] = 'date'


class DevolucaoFilter(django_filters.FilterSet):
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
        for field in self.form.fields.values():
            field.widget.attrs.update({'class': 'form-control form-control-sm'})
        self.form.fields['data_devolucao__gte'].widget.attrs['type'] = 'date'
        self.form.fields['data_devolucao__lte'].widget.attrs['type'] = 'date'


class ContingenciaFilter(django_filters.FilterSet):
    processo__id = django_filters.NumberFilter(label="Nº do Processo")
    solicitante__username = django_filters.CharFilter(lookup_expr='icontains', label="Solicitante")
    status = django_filters.ChoiceFilter(choices=STATUS_CONTINGENCIA, label="Status", empty_label="Todos os Status")

    class Meta:
        model = Contingencia
        fields = ['processo__id', 'solicitante__username', 'status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.form.fields.values():
            field.widget.attrs.update({'class': 'form-control form-control-sm'})
