"""Formulários de entrada para verbas indenizatórias.

Este módulo define formulários para cadastro, edição e validação de diárias, reembolsos, jetons e auxílios.
"""

from django import forms
from verbas_indenizatorias.models import Diaria, ReembolsoCombustivel, Jeton, AuxilioRepresentacao


class DiariaForm(forms.ModelForm):
    """Formulário de diárias com valor total calculável no servidor."""

    class Meta:
        model = Diaria
        fields = ['data_solicitacao', 'beneficiario', 'proponente', 'tipo_solicitacao', 'diaria_inicial', 'data_saida', 'data_retorno', 'cidade_origem', 'cidade_destino', 'objetivo', 'meio_de_transporte', 'quantidade_diarias', 'valor_total']
        widgets = {
            'data_solicitacao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'beneficiario': forms.Select(attrs={'class': 'form-select'}),
            'proponente': forms.Select(attrs={'class': 'form-select'}),
            'tipo_solicitacao': forms.Select(attrs={'class': 'form-select'}),
            'diaria_inicial': forms.Select(attrs={'class': 'form-select'}),
            'data_saida': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_retorno': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'cidade_origem': forms.TextInput(attrs={'class': 'form-control'}),
            'cidade_destino': forms.TextInput(attrs={'class': 'form-control'}),
            'objetivo': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'meio_de_transporte': forms.Select(attrs={'class': 'form-select'}),
            'quantidade_diarias': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'readonly': 'readonly'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': 'readonly', 'id': 'id_valor_total'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['diaria_inicial'].required = False
        self.fields['diaria_inicial'].queryset = Diaria.objects.none()
        self.fields['diaria_inicial'].help_text = 'Obrigatório apenas para complementação.'

        beneficiario_id = None
        if self.is_bound:
            beneficiario_id = self.data.get('beneficiario')
        elif self.instance and self.instance.beneficiario_id:
            beneficiario_id = self.instance.beneficiario_id

        if beneficiario_id:
            try:
                beneficiario_id = int(beneficiario_id)
                qs = Diaria.objects.filter(
                    beneficiario_id=beneficiario_id,
                    tipo_solicitacao='INICIAL',
                ).order_by('-data_solicitacao', '-id')
                if self.instance and self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                self.fields['diaria_inicial'].queryset = qs
            except (TypeError, ValueError):
                self.fields['diaria_inicial'].queryset = Diaria.objects.none()

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
        fields = ['numero_sequencial', 'processo', 'diaria', 'beneficiario', 'data_saida', 'data_retorno', 'cidade_origem', 'cidade_destino', 'distancia_km', 'preco_combustivel', 'objetivo', 'valor_total']
        widgets = {
            'numero_sequencial': forms.TextInput(attrs={'class': 'form-control'}),
            'processo': forms.Select(attrs={'class': 'form-select'}),
            'diaria': forms.Select(attrs={'class': 'form-select'}),
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
        fields = ['numero_sequencial', 'processo', 'beneficiario', 'reuniao', 'valor_total']
        widgets = {
            'numero_sequencial': forms.TextInput(attrs={'class': 'form-control'}),
            'processo': forms.Select(attrs={'class': 'form-select'}),
            'beneficiario': forms.Select(attrs={'class': 'form-select'}),
            'reuniao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Março/2026 ou 15ª Sessão'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class AuxilioForm(forms.ModelForm):
    """Formulário para auxílios de representação."""

    class Meta:
        model = AuxilioRepresentacao
        fields = ['numero_sequencial', 'processo', 'beneficiario', 'objetivo', 'valor_total']
        widgets = {
            'numero_sequencial': forms.TextInput(attrs={'class': 'form-control'}),
            'processo': forms.Select(attrs={'class': 'form-select'}),
            'beneficiario': forms.Select(attrs={'class': 'form-select'}),
            'objetivo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Motivo ou evento da representação'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
