"""Formulários de entrada para verbas indenizatórias.

Este módulo define formulários para cadastro, edição e validação de diárias, reembolsos, jetons e auxílios.
"""

from django import forms
from django.forms import inlineformset_factory
from verbas_indenizatorias.models import (
    Diaria,
    ReembolsoCombustivel,
    Jeton,
    AuxilioRepresentacao,
    DevolucaoDiaria,
    ContingenciaDiaria,
    PrestacaoContasDiaria,
    DocumentoComprovacao,
    _CAMPOS_PERMITIDOS_CONTINGENCIA_DIARIA,
)


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


class DiariaComSolicitacaoAssinadaForm(DiariaForm):
    """Entrada alternativa de diária com solicitação já assinada anexada pelo operador."""

    solicitacao_assinada_arquivo = forms.FileField(
        label="Solicitação assinada (PDF)",
        required=True,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf'}),
        help_text='Anexe o PDF da solicitação já assinada para cadastro direto da diária.',
    )

    def clean_solicitacao_assinada_arquivo(self):
        arquivo = self.cleaned_data.get('solicitacao_assinada_arquivo')
        if not arquivo:
            raise forms.ValidationError('Anexe a solicitação assinada.')

        nome = (arquivo.name or '').lower()
        if not nome.endswith('.pdf'):
            raise forms.ValidationError('A solicitação assinada deve ser enviada em PDF.')
        return arquivo


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
        fields = ['numero_sequencial', 'processo', 'beneficiario', 'reuniao', 'data_evento', 'local_evento', 'valor_total']
        widgets = {
            'numero_sequencial': forms.TextInput(attrs={'class': 'form-control'}),
            'processo': forms.Select(attrs={'class': 'form-select'}),
            'beneficiario': forms.Select(attrs={'class': 'form-select'}),
            'reuniao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Março/2026 ou 15ª Sessão'}),
            'data_evento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'local_evento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Local de realização da reunião/sessão'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class AuxilioForm(forms.ModelForm):
    """Formulário para auxílios de representação."""

    class Meta:
        model = AuxilioRepresentacao
        fields = ['numero_sequencial', 'processo', 'beneficiario', 'objetivo', 'data_evento', 'local_evento', 'valor_total']
        widgets = {
            'numero_sequencial': forms.TextInput(attrs={'class': 'form-control'}),
            'processo': forms.Select(attrs={'class': 'form-select'}),
            'beneficiario': forms.Select(attrs={'class': 'form-select'}),
            'objetivo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Motivo ou evento da representação'}),
            'data_evento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'local_evento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Local do evento ou ato de representação'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


ComprovanteDiariaFormSet = inlineformset_factory(
    PrestacaoContasDiaria,
    DocumentoComprovacao,
    fields=['tipo', 'ordem', 'arquivo'],
    extra=1,
    can_delete=True,
    widgets={
        'tipo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        'ordem': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'style': 'width: 60px'}),
        'arquivo': forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm'}),
    },
)


class DevolucaoDiariaForm(forms.ModelForm):
    """Formulário para registrar uma devolução vinculada a uma diária."""

    class Meta:
        model = DevolucaoDiaria
        fields = ['valor_devolvido', 'data_devolucao', 'motivo']
        widgets = {
            'valor_devolvido': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'data_devolucao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'motivo': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


_CAMPO_CHOICES = [('', '---------')] + sorted(
    [(c, c) for c in _CAMPOS_PERMITIDOS_CONTINGENCIA_DIARIA]
)


class ContingenciaDiariaForm(forms.Form):
    """Formulário para abrir uma contingência de retificação em uma diária."""

    campo_corrigido = forms.ChoiceField(
        label="Campo a Corrigir",
        choices=_CAMPO_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    valor_anterior = forms.CharField(
        label="Valor Atual (referência)",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    valor_proposto = forms.CharField(
        label="Novo Valor",
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    justificativa = forms.CharField(
        label="Justificativa",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
    )

    def clean_campo_corrigido(self):
        campo = self.cleaned_data.get('campo_corrigido')
        if campo not in _CAMPOS_PERMITIDOS_CONTINGENCIA_DIARIA:
            raise forms.ValidationError("Campo não permitido para retificação via contingência.")
        return campo
