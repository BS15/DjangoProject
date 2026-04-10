"""Formulários de entrada para suprimentos de fundos."""

from django import forms
from suprimentos.models import SuprimentoDeFundos
from fluxo.validators import validar_regras_suprimento


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
