"""Formulários de entrada para cadastro e manutenção de credores.

Este módulo define formulários para entrada, edição e validação de dados de credores e contas bancárias.
"""

import re

from django import forms
from credores.models import Credor, ContaFixa


class CredorForm(forms.ModelForm):
    """Formulário de cadastro de credores com dados bancários e serviço padrão."""

    class Meta:
        model = Credor
        fields = ['tipo', 'cpf_cnpj', 'nome', 'telefone', 'email', 'conta', 'chave_pix', 'cargo_funcao', 'codigo_servico_padrao']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'cpf_cnpj': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apenas números'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control mask-telefone', 'placeholder': '(00) 00000-0000'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'cargo_funcao': forms.Select(attrs={'class': 'form-select'}),
            'conta': forms.Select(attrs={'class': 'form-select'}),
            'chave_pix': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_servico_padrao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 100000001'}),
        }

    def clean_cpf_cnpj(self):
        """Valida tamanho do documento conforme tipo de pessoa selecionado."""
        valor = self.cleaned_data.get('cpf_cnpj', '')
        tipo = self.cleaned_data.get('tipo')
        documento = re.sub(r'\D', '', valor)

        if tipo == 'PF' and len(documento) != 11:
            raise forms.ValidationError('Para Pessoa Física, informe um CPF com 11 dígitos.')

        if tipo == 'PJ' and len(documento) != 14:
            raise forms.ValidationError('Para Pessoa Jurídica, informe um CNPJ com 14 dígitos.')

        return valor


class CredorEditForm(forms.ModelForm):
    """Formulário de manutenção sem permitir alteração de CPF/CNPJ."""

    class Meta:
        model = Credor
        fields = [
            'nome',
            'telefone',
            'email',
            'conta',
            'chave_pix',
            'cargo_funcao',
            'codigo_servico_padrao',
        ]
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control mask-telefone', 'placeholder': '(00) 00000-0000'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'conta': forms.Select(attrs={'class': 'form-select'}),
            'chave_pix': forms.TextInput(attrs={'class': 'form-control'}),
            'cargo_funcao': forms.Select(attrs={'class': 'form-select'}),
            'codigo_servico_padrao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 100000001'}),
        }



# Formulário ContaFixaForm migrado para pagamentos.support.conta_fixa_forms
