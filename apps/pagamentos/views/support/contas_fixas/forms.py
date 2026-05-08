"""Formulários de conta fixa."""

from django import forms

from credores.models import ContaFixa


class ContaFixaForm(forms.ModelForm):
    class Meta:
        model = ContaFixa
        fields = ["credor", "referencia", "dia_vencimento", "data_inicio", "ativa"]
        widgets = {
            "credor": forms.Select(attrs={"class": "form-select"}),
            "referencia": forms.TextInput(attrs={"class": "form-control"}),
            "dia_vencimento": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 31}),
            "data_inicio": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "ativa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


__all__ = ["ContaFixaForm"]
