"""Formulários de entrada para documentos fiscais e retenções.

Este módulo define formulários para cadastro, edição e validação de notas fiscais e retenções de impostos.
"""

from django import forms
from django.forms import inlineformset_factory
from fiscal.models import DocumentoFiscal, RetencaoImposto
from pagamentos.domain_models import Processo


class DocumentoFiscalForm(forms.ModelForm):
    """Formulário de nota fiscal com campos mínimos para ateste e retenções."""

    def __init__(self, *args, **kwargs):
        """Define obrigatoriedade e restringe fiscal aos usuários do grupo apropriado."""
        super().__init__(*args, **kwargs)
        self.fields['numero_nota_fiscal'].required = True
        self.fields['nome_emitente'].required = True
        self.fields['data_emissao'].required = True
        self.fields['valor_bruto'].required = True
        self.fields['valor_liquido'].required = True

    class Meta:
        model = DocumentoFiscal
        fields = ['nome_emitente', 'cnpj_emitente', 'serie_nota_fiscal', 'numero_nota_fiscal', 'data_emissao', 'valor_bruto', 'valor_liquido', 'atestada', 'codigo_servico_inss']
        widgets = {
            'nome_emitente': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'cnpj_emitente': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'serie_nota_fiscal': forms.TextInput(attrs={'class': 'form-control form-select-sm', 'placeholder': 'Ex: A1'}),
            'numero_nota_fiscal': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'data_emissao': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
            'valor_bruto': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'valor_liquido': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'atestada': forms.CheckboxInput(attrs={'class': 'form-check-input fs-5'}),
            'codigo_servico_inss': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Somente quando há retenção INSS'}),
        }


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