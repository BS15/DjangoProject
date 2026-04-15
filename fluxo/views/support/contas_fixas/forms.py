"""Formulários de contas fixas."""

from django import forms

from credores.models import ContaFixa


class ContaFixaForm(forms.ModelForm):
    """Formulário para manutenção de contas fixas com vencimento mensal."""

    class Meta:
        model = ContaFixa
        fields = ["credor", "referencia", "dia_vencimento", "ativa", "data_inicio"]
        widgets = {
            "credor": forms.Select(attrs={"class": "form-select"}),
            "referencia": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: Conta de Luz - Sede"}),
            "dia_vencimento": forms.NumberInput(attrs={"class": "form-control", "min": "1", "max": "31"}),
            "ativa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "data_inicio": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }

__all__ = ["ContaFixaForm"]