"""Formulários de entrada para cadastro e manutenção de credores.

Este módulo define formulários para entrada, edição e validação de dados de credores e contas bancárias.
"""

from django import forms
from django.contrib.auth import get_user_model

from credores.models import Credor, ContaFixa, ContasBancarias

User = get_user_model()


def _usuarios_disponiveis(exclude_credor_pk=None):
    """Retorna queryset de usuários sem credor vinculado, opcionalmente preservando o do credor informado."""
    qs = User.objects.filter(is_active=True).order_by('username')
    taken = Credor.objects.exclude(usuario__isnull=True).values_list('usuario_id', flat=True)
    if exclude_credor_pk:
        taken = taken.exclude(pk=exclude_credor_pk)
    return qs.exclude(pk__in=taken)


class CredorForm(forms.ModelForm):
    """Formulário de cadastro de credores com dados bancários e serviço padrão."""
    
    banco = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Banco do Brasil'}), label="Banco")
    agencia = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 1234-5'}), label="Agência")
    conta_numero = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 12345-6'}), label="Conta Corrente")

    def __init__(self, *args, **kwargs):
        """Inicializa o formulário filtrando usuários ainda não vinculados a credor."""
        super().__init__(*args, **kwargs)
        self.fields['usuario'].queryset = _usuarios_disponiveis()
        self.fields['usuario'].empty_label = "— Sem usuário vinculado —"

    def save(self, commit=True):
        credor = super().save(commit=False)
        if commit:
            credor.save()
            banco_val = self.cleaned_data.get('banco')
            agencia_val = self.cleaned_data.get('agencia')
            conta_val = self.cleaned_data.get('conta_numero')
            
            if banco_val or agencia_val or conta_val:
                conta_obj = ContasBancarias.objects.create(
                    titular=credor,
                    banco=banco_val or '',
                    agencia=agencia_val or '',
                    conta=conta_val or '',
                )
                credor.conta = conta_obj
                credor.save(update_fields=['conta'])
        return credor

    class Meta:
        model = Credor
        fields = ['tipo', 'cpf_cnpj', 'nome', 'telefone', 'email', 'chave_pix', 'cargo_funcao', 'codigo_servico_padrao', 'usuario']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'cpf_cnpj': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apenas números'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control mask-telefone', 'placeholder': '(00) 00000-0000'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'cargo_funcao': forms.Select(attrs={'class': 'form-select'}),
            'chave_pix': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_servico_padrao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 100000001'}),
            'usuario': forms.Select(attrs={'class': 'form-select'}),
        }

class CredorEditForm(forms.ModelForm):
    """Formulário de manutenção sem permitir alteração de CPF/CNPJ e tipo."""

    banco = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Banco do Brasil'}), label="Banco")
    agencia = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 1234-5'}), label="Agência")
    conta_numero = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 12345-6'}), label="Conta Corrente")

    def __init__(self, *args, **kwargs):
        """Inicializa o formulário de edição preservando o usuário do credor atual e preenchendo os dados bancários."""
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        credor_pk = instance.pk if instance else None
        self.fields['usuario'].queryset = _usuarios_disponiveis(exclude_credor_pk=credor_pk)
        self.fields['usuario'].empty_label = "— Sem usuário vinculado —"

        if instance and instance.conta:
            self.initial['banco'] = instance.conta.banco
            self.initial['agencia'] = instance.conta.agencia
            self.initial['conta_numero'] = instance.conta.conta

    def save(self, commit=True):
        credor = super().save(commit=False)
        if commit:
            credor.save()
            banco_val = self.cleaned_data.get('banco')
            agencia_val = self.cleaned_data.get('agencia')
            conta_val = self.cleaned_data.get('conta_numero')
            
            if banco_val or agencia_val or conta_val:
                if credor.conta:
                    # Update existing linked conta
                    conta_obj = credor.conta
                    conta_obj.banco = banco_val or ''
                    conta_obj.agencia = agencia_val or ''
                    conta_obj.conta = conta_val or ''
                    conta_obj.save()
                else:
                    # Create new conta
                    conta_obj = ContasBancarias.objects.create(
                        titular=credor,
                        banco=banco_val or '',
                        agencia=agencia_val or '',
                        conta=conta_val or '',
                    )
                    credor.conta = conta_obj
                    credor.save(update_fields=['conta'])
            else:
                # User cleared the fields, maybe they want to detach? Let's detach.
                if credor.conta:
                    credor.conta = None
                    credor.save(update_fields=['conta'])
        return credor

    class Meta:
        model = Credor
        fields = [
            'nome',
            'email',
            'telefone',
            'cargo_funcao',
            'usuario',
            'chave_pix',
            'codigo_servico_padrao',
        ]
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control mask-telefone', 'placeholder': '(00) 00000-0000'}),
            'cargo_funcao': forms.Select(attrs={'class': 'form-select'}),
            'usuario': forms.Select(attrs={'class': 'form-select'}),
            'chave_pix': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Chave PIX'}),
            'codigo_servico_padrao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 100000001'}),
        }



# Formulário ContaFixaForm migrado para pagamentos.support.conta_fixa_forms
