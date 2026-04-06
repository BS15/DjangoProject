"""Formulários de entrada e validação para fluxos financeiros e administrativos."""

from django import forms
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from django.contrib.auth.models import User
from .models.segments.core import Processo, Diaria, ReembolsoCombustivel, Jeton, AuxilioRepresentacao, SuprimentoDeFundos
from .models.segments.documents import DocumentoProcesso, DocumentoFiscal
from .models.segments.auxiliary import RetencaoImposto, Pendencia, Devolucao
from .models.segments.cadastros import Credor, DadosContribuinte, ContasBancarias, ContaFixa
from .models.segments.parametrizations import StatusChoicesPendencias, TiposDePagamento
from .validators import validar_regras_processo, validar_regras_suprimento, STATUS_BLOQUEADOS_FORM

SUPRIMENTO_DE_FUNDOS = 'SUPRIMENTO DE FUNDOS'

class ProcessoForm(forms.ModelForm):
    """Formulário principal de Processo com bloqueios por estágio e filtros de domínio."""

    class Meta:
        model = Processo
        exclude = ['status']
        widgets = {
            'extraorcamentario': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'n_nota_empenho': forms.TextInput(attrs={'class': 'form-control'}),
            'credor': forms.Select(attrs={'class': 'form-select'}),
            'ano_exercicio': forms.Select(attrs={'class': 'form-select'}),
            'data_empenho': forms.DateInput(format='%Y-%m-%d',attrs={'type': 'date', 'class': 'form-control'}),
            'conta': forms.Select(attrs={'class': 'form-select'}),
            'tipo_pagamento': forms.Select(attrs={'class': 'form-select'}),
            'forma_pagamento': forms.Select(attrs={'class': 'form-select'}),
            'data_pagamento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'data_vencimento': forms.DateInput(format='%Y-%m-%d',attrs={'type': 'date', 'class': 'form-control'}),
            'valor_bruto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'valor_liquido': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'detalhamento': forms.TextInput(attrs={'class': 'form-control'}),
            'observacao': forms.TextInput(attrs={'class': 'form-control'}),
            'tag': forms.Select(attrs={'class': 'form-select'})
        }

    def __init__(self, *args, **kwargs):
        """Configura obrigatoriedade, travas por status e querysets contextuais."""
        super().__init__(*args, **kwargs)

        campos_obrigatorios = [
            'credor', 'valor_bruto', 'valor_liquido',
            'data_vencimento', 'data_pagamento',
            'tipo_pagamento', 'forma_pagamento'
        ]

        for field_name in self.fields:
            if field_name in campos_obrigatorios:
                self.fields[field_name].required = True
            else:
                self.fields[field_name].required = False

        self.status_bloqueados = STATUS_BLOQUEADOS_FORM

        if self.instance and self.instance.pk and self.instance.status:
            status_atual = self.instance.status.status_choice.upper()

            if status_atual in self.status_bloqueados:

                for campo in ['valor_liquido', 'valor_bruto']:
                    if campo in self.fields:
                        self.fields[campo].widget.attrs['readonly'] = True
                        self.fields[campo].widget.attrs['class'] = self.fields[campo].widget.attrs.get('class', '') + ' bg-light'

                if 'credor' in self.fields:
                    self.fields['credor'].widget.attrs['disabled'] = 'disabled'
                    self.fields['credor'].widget.attrs['class'] = self.fields['credor'].widget.attrs.get('class', '') + ' bg-light'
                    self.fields['credor'].required = False

        qs = TiposDePagamento.objects.exclude(tipo_de_pagamento__iexact=SUPRIMENTO_DE_FUNDOS)
        if self.instance and self.instance.pk and self.instance.tipo_pagamento:
            if self.instance.tipo_pagamento.tipo_de_pagamento.upper() == SUPRIMENTO_DE_FUNDOS:
                qs = TiposDePagamento.objects.all()
        self.fields['tipo_pagamento'].queryset = qs

        contribuinte = DadosContribuinte.objects.first()
        if contribuinte:
            self.fields['conta'].queryset = ContasBancarias.objects.filter(
                titular__cpf_cnpj=contribuinte.cnpj
            )
        else:
            self.fields['conta'].queryset = ContasBancarias.objects.none()

    def clean_credor(self):
        """Preserva o credor original quando o processo está em estágio bloqueado."""
        credor_enviado = self.cleaned_data.get('credor')
        if self.instance and self.instance.pk and self.instance.status:
            if self.instance.status.status_choice.upper() in getattr(self, 'status_bloqueados', []):
                return self.instance.credor
        return credor_enviado

    def clean_valor_liquido(self):
        """Evita alteração de valor líquido em estágios bloqueados."""
        valor_enviado = self.cleaned_data.get('valor_liquido')
        if self.instance and self.instance.pk and self.instance.status:
            if self.instance.status.status_choice.upper() in getattr(self, 'status_bloqueados', []):
                return self.instance.valor_liquido
        return valor_enviado

    def clean_valor_bruto(self):
        """Evita alteração de valor bruto em estágios bloqueados."""
        valor_enviado = self.cleaned_data.get('valor_bruto')
        if self.instance and self.instance.pk and self.instance.status:
            if self.instance.status.status_choice.upper() in getattr(self, 'status_bloqueados', []):
                return self.instance.valor_bruto
        return valor_enviado

    def clean(self):
        """Aplica validações de negócio do processo e agrega erros no formulário."""
        cleaned_data = super().clean()

        try:
            erros_processo = validar_regras_processo(cleaned_data)
            if erros_processo:
                for field, error in erros_processo.items():
                    self.add_error(field, error)
        except NameError:
            pass

        return cleaned_data

class DocumentoFiscalForm(forms.ModelForm):
    """Formulário de nota fiscal com campos mínimos para ateste e retenções."""

    arquivo_ia = forms.FileField(
        required=False,
        label="Extrair via IA",
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control form-control-sm extrair-ia-input',
            'accept': 'application/pdf'
        })
    )

    def __init__(self, *args, **kwargs):
        """Define obrigatoriedade e restringe fiscal aos usuários do grupo apropriado."""
        super().__init__(*args, **kwargs)
        self.fields['numero_nota_fiscal'].required = True
        self.fields['nome_emitente'].required = True
        self.fields['data_emissao'].required = True
        self.fields['valor_bruto'].required = True
        self.fields['valor_liquido'].required = True
        if 'fiscal_contrato' in self.fields:
            self.fields['fiscal_contrato'].queryset = User.objects.filter(groups__name='FISCAL DE CONTRATO')

    class Meta:
        model = DocumentoFiscal
        fields = ['nome_emitente', 'cnpj_emitente', 'serie_nota_fiscal', 'numero_nota_fiscal', 'data_emissao', 'valor_bruto', 'valor_liquido', 'fiscal_contrato', 'atestada', 'codigo_servico_inss']
        widgets = {
            'nome_emitente': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'cnpj_emitente': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'serie_nota_fiscal': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Ex: A1'}),
            'numero_nota_fiscal': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'data_emissao': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
            'valor_bruto': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'valor_liquido': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'fiscal_contrato': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'atestada': forms.CheckboxInput(attrs={'class': 'form-check-input fs-5'}),
            'codigo_servico_inss': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Somente quando há retenção INSS'}),
        }

DocumentoFormSet = inlineformset_factory(
    Processo,
    DocumentoProcesso,
    fields=['tipo', 'ordem', 'arquivo'],
    extra=1,
    can_delete=True,
    widgets={
        'tipo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        'ordem': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'style': 'width: 60px'}),
        'arquivo': forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm'}),
    }
)

DocumentoFiscalFormSet = inlineformset_factory(
    Processo,
    DocumentoFiscal,
    form=DocumentoFiscalForm,
    extra=0,
    can_delete=True
)

RetencaoFormSet = inlineformset_factory(
    DocumentoFiscal,
    RetencaoImposto,
    fields=['beneficiario', 'codigo', 'rendimento_tributavel', 'valor'],
    widgets={
        'beneficiario': forms.Select(attrs={'class': 'form-select form-select-sm tax-beneficiario-select'}),
        'codigo': forms.Select(attrs={'class': 'form-select form-select-sm tax-code-select'}),
        'rendimento_tributavel': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'style': 'width: 100px', 'placeholder': 'Rendimento R$'}),
        'valor': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'style': 'width: 100px', 'placeholder': 'Imposto R$'})
    },
    extra=1,
    can_delete=True
)

class CredorForm(forms.ModelForm):
    """Formulário de cadastro de credores com dados bancários e serviço padrão."""

    class Meta:
        model = Credor
        fields = ['tipo', 'cpf_cnpj', 'nome', 'telefone', 'email', 'conta', 'chave_pix', 'cargo_funcao', 'codigo_servico_padrao']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'cpf_cnpj': forms.TextInput(attrs={'class': 'form-control mask-cpf-cnpj', 'placeholder': 'Apenas números'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control mask-telefone', 'placeholder': '(00) 00000-0000'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'cargo_funcao': forms.Select(attrs={'class': 'form-select'}),
            'conta': forms.Select(attrs={'class': 'form-select'}),
            'chave_pix': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_servico_padrao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 100000001'}),
        }

class DiariaForm(forms.ModelForm):
    """Formulário de diárias com valor total calculável no servidor."""

    class Meta:
        model = Diaria
        fields = ['numero_siscac', 'processo', 'beneficiario', 'proponente', 'tipo_solicitacao', 'data_saida', 'data_retorno', 'cidade_origem', 'cidade_destino', 'objetivo', 'meio_de_transporte', 'quantidade_diarias', 'valor_total']
        widgets = {
            'numero_siscac': forms.TextInput(attrs={'class': 'form-control'}),
            'processo': forms.Select(attrs={'class': 'form-select'}),
            'beneficiario': forms.Select(attrs={'class': 'form-select'}),
            'proponente': forms.Select(attrs={'class': 'form-select'}),
            'tipo_solicitacao': forms.Select(attrs={'class': 'form-select'}),
            'data_saida': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_retorno': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'cidade_origem': forms.TextInput(attrs={'class': 'form-control'}),
            'cidade_destino': forms.TextInput(attrs={'class': 'form-control'}),
            'objetivo': forms.TextInput(attrs={'class': 'form-control'}),
            'meio_de_transporte': forms.Select(attrs={'class': 'form-select'}),
            'quantidade_diarias': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': 'readonly', 'id': 'id_valor_total'}),
        }

    def clean(self):
        """Permite valor total vazio para cenários de cálculo automático posterior."""
        cleaned_data = super().clean()
        if not cleaned_data.get('valor_total'):
            cleaned_data['valor_total'] = None
        return cleaned_data

class ReembolsoForm(forms.ModelForm):
    """Formulário de reembolso de combustível com dados de deslocamento."""
    class Meta:
        model = ReembolsoCombustivel
        fields = ['numero_sequencial', 'processo', 'diaria', 'status', 'beneficiario', 'data_saida', 'data_retorno', 'cidade_origem', 'cidade_destino', 'distancia_km', 'preco_combustivel', 'objetivo', 'valor_total']
        widgets = {
            'numero_sequencial': forms.TextInput(attrs={'class': 'form-control'}),
            'processo': forms.Select(attrs={'class': 'form-select'}),
            'diaria': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'beneficiario': forms.Select(attrs={'class': 'form-select'}),
            'data_saida': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_retorno': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'cidade_origem': forms.TextInput(attrs={'class': 'form-control'}),
            'cidade_destino': forms.TextInput(attrs={'class': 'form-control'}),
            'distancia_km': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'preco_combustivel': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'objetivo': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class JetonForm(forms.ModelForm):
    """Formulário para lançamentos de jeton."""
    class Meta:
        model = Jeton
        fields = ['numero_sequencial', 'processo', 'status', 'beneficiario', 'reuniao', 'valor_total']
        widgets = {
            'numero_sequencial': forms.TextInput(attrs={'class': 'form-control'}),
            'processo': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'beneficiario': forms.Select(attrs={'class': 'form-select'}),
            'reuniao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Março/2026 ou 15ª Sessão'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class AuxilioForm(forms.ModelForm):
    """Formulário para auxílios de representação."""
    class Meta:
        model = AuxilioRepresentacao
        fields = ['numero_sequencial', 'processo', 'status', 'beneficiario', 'objetivo', 'valor_total']
        widgets = {
            'numero_sequencial': forms.TextInput(attrs={'class': 'form-control'}),
            'processo': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'beneficiario': forms.Select(attrs={'class': 'form-select'}),
            'objetivo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Motivo ou evento da representação'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class SuprimentoForm(forms.ModelForm):
    """Formulário de suprimento de fundos com validações específicas do regime."""

    class Meta:
        model = SuprimentoDeFundos
        fields = ['suprido', 'lotacao', 'valor_liquido', 'taxa_saque', 'data_saida', 'data_retorno', 'data_recibo']
        widgets = {
            'data_saida': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_retorno': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_recibo': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'valor_liquido': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'taxa_saque': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'suprido': forms.Select(attrs={'class': 'form-select'}),
            'lotacao': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        """Executa validações de negócio de suprimento e propaga erros por campo."""
        cleaned_data = super().clean()
        erros_suprimento = validar_regras_suprimento(cleaned_data)
        if erros_suprimento:
            for field, error in erros_suprimento.items():
                self.add_error(field, error)
        return cleaned_data

class PendenciaForm(forms.ModelForm):
    """Formulário de pendência que injeta status padrão na criação."""

    class Meta:
        model = Pendencia
        fields = ['tipo', 'descricao']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Descreva a pendência detalhadamente...'}),
        }

    def save(self, commit=True):
        """Salva pendência e garante status inicial ``A RESOLVER`` quando ausente."""
        pendencia = super().save(commit=False)

        if not pendencia.status:
            status_obj, _ = StatusChoicesPendencias.objects.get_or_create(
                status_choice__iexact='A RESOLVER',
                defaults={'status_choice': 'A RESOLVER'}
            )
            pendencia.status = status_obj

        if commit:
            pendencia.save()
        return pendencia

PendenciaFormSet = inlineformset_factory(
    Processo, Pendencia,
    form=PendenciaForm,
    extra=1,
    can_delete=True
)

class DevolucaoForm(forms.ModelForm):
    """Formulário para registrar devoluções vinculadas a um processo."""

    class Meta:
        model = Devolucao
        fields = ['valor_devolvido', 'data_devolucao', 'motivo', 'comprovante']
        widgets = {
            'valor_devolvido': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'data_devolucao': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'motivo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'comprovante': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

class ContaFixaForm(forms.ModelForm):
    """Formulário para manutenção de contas fixas com vencimento mensal."""

    class Meta:
        model = ContaFixa
        fields = ['credor', 'referencia', 'dia_vencimento', 'ativa', 'data_inicio']
        widgets = {
            'credor': forms.Select(attrs={'class': 'form-select'}),
            'referencia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Conta de Luz - Sede'}),
            'dia_vencimento': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '31'}),
            'ativa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'data_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
