"""Formulários de entrada para suprimentos de fundos.

Este módulo define formulários para cadastro, edição e validação de suprimentos de fundos e despesas relacionadas.
"""

from django import forms
from suprimentos.models import SuprimentoDeFundos, PrestacaoContasSuprimento
from pagamentos.validators import validar_regras_suprimento
from suprimentos.models import DespesaSuprimento


class SuprimentoForm(forms.ModelForm):
    """Formulário de suprimento de fundos com validações específicas do regime."""

    class Meta:
        model = SuprimentoDeFundos
        fields = ['suprido', 'lotacao', 'valor_liquido', 'taxa_saque', 'inicio_periodo', 'fim_periodo', 'data_recibo']
        widgets = {
            'inicio_periodo': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fim_periodo': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
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


class EnviarPrestacaoSuprimentoForm(forms.Form):
    """Formulário de envio da prestação de contas do suprimento de fundos.

    Coleta o comprovante de devolução de saldo, a data e o aceite do termo de fidedignidade.
    """

    comprovante_devolucao = forms.FileField(
        label="Comprovante de Devolução de Saldo (GRU/Depósito)",
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf'}),
        help_text="Obrigatório quando houver saldo remanescente. Anexe o comprovante bancário da devolução.",
    )
    data_devolucao = forms.DateField(
        label="Data da Devolução do Saldo",
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    confirma_fidedignidade = forms.BooleanField(
        label=(
            "Declaro, sob responsabilidade pessoal, que todas as despesas registradas "
            "neste suprimento de fundos são legítimas, comprovadas e estão de acordo "
            "com a legislação vigente."
        ),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={'required': 'Você deve confirmar a fidedignidade dos dados para enviar a prestação.'},
    )
