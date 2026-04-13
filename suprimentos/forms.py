"""Formulários de entrada para suprimentos de fundos.

Este módulo define formulários para cadastro, edição e validação de suprimentos de fundos e despesas relacionadas.
"""

from django import forms
from suprimentos.models import SuprimentoDeFundos
from fluxo.validators import validar_regras_suprimento
from suprimentos.models import DespesaSuprimento


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



class DespesaSuprimentoForm(forms.ModelForm):
    """Formulário para registrar uma despesa individual em um suprimento de fundos."""

    class Meta:
        model = DespesaSuprimento
        fields = ['data', 'estabelecimento', 'cnpj_cpf', 'nota_fiscal', 'detalhamento', 'valor', 'arquivo']
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
            'estabelecimento': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'cnpj_cpf': forms.TextInput(attrs={'class': 'form-control form-control-sm mask-cpf-cnpj', 'placeholder': 'Opcional'}),
            'nota_fiscal': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'detalhamento': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2}),
            'valor': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control form-control-sm'}),
            'arquivo': forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm', 'accept': '.pdf'}),
        }
