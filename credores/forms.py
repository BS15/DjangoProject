"""Formulários de entrada para cadastro e manutenção de credores.

Este módulo define formulários para entrada, edição e validação de dados de credores e contas bancárias.
"""

from django import forms
from credores.models import Credor, ContaFixa


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



# Formulário ContaFixaForm migrado para fluxo.support.conta_fixa_forms
