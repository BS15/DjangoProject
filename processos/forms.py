from django import forms
from django.forms import inlineformset_factory
from .models import Processo, DocumentoProcesso, NotaFiscal, RetencaoImposto, Credor, Diaria, ReembolsoCombustivel, Jeton, AuxilioRepresentacao

class ProcessoForm(forms.ModelForm):
    class Meta:
        model = Processo
        # Traz todos os campos do model, exceto o status
        exclude = ['status']
        widgets = {
            'extraorcamentario': forms.CheckboxInput(attrs={'class': 'form-control'}),
            'n_nota_empenho': forms.TextInput(attrs={'class': 'form-control'}),
            'credor': forms.TextInput(attrs={'class': 'form-control'}),
            'ano_exercicio': forms.Select(attrs={'class': 'form-select'}),
            'data_empenho': forms.DateInput(format='%Y-%m-%d',attrs={'type': 'date', 'class': 'form-control'}),
            'conta_de_pagamento_orgao': forms.Select(attrs={'class': 'form-select'}),
            'tipo_pagamento': forms.Select(attrs={'class': 'form-select'}),
            'forma_pagamento': forms.Select(attrs={'class': 'form-select'}),
            'data_pagamento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'data_vencimento': forms.DateInput(format='%Y-%m-%d',attrs={'type': 'date', 'class': 'form-control'}),
            'valor_bruto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'valor_liquido': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'codigo_barras': forms.TextInput(attrs={'class': 'form-control'}),
            'detalhamento': forms.TextInput(attrs={'class': 'form-control'}),
            'observacao': forms.TextInput(attrs={'class': 'form-control'}),
            'tag': forms.Select(attrs={'class': 'form-select'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Loop que percorre todos os campos gerados e desliga a obrigatoriedade (HTML required)
        for field_name, field in self.fields.items():
            field.required = False

class NotaFiscalForm(forms.ModelForm):
    class Meta:
        model = NotaFiscal
        fields = ('data_emissao',
                  'nome_emitente',
                  'cnpj_emitente',
                  'numero_nota_fiscal',
                  'valor_bruto',
                  'valor_liquido')

        widgets = {
            'data_emissao': forms.DateInput(format='%Y-%m-%d',attrs={'type': 'date', 'class': 'form-control'}),
            'nome_emitente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Razão Social'}),
            'cnpj_emitente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00.000.000/0000-00'}),
            'numero_nota_fiscal': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_bruto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'valor_liquido': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
        }

DocumentoFormSet = inlineformset_factory(
    Processo,
    DocumentoProcesso,
    fields=['tipo',
            'ordem',
            'arquivo'],
    extra=1, # Start with 1 empty row
    can_delete=True,
    widgets={
        'tipo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        'ordem': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'style': 'width: 60px'}),
        'arquivo': forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm'}),
    }
)

# Logic: 1 Process has Many Fiscal Notes
NotaFiscalFormSet = inlineformset_factory(
    Processo,
    NotaFiscal,
    form=NotaFiscalForm,
    extra=0, # Start with 0, we will add via JS
    can_delete=True
)

RetencaoFormSet = inlineformset_factory(
    NotaFiscal,
    RetencaoImposto,
    fields=['codigo', 'valor'],
    widgets={
        'codigo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        'valor': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'style': 'width: 60px'})
    },
    extra=1,
    can_delete=True
)

class CredorForm(forms.ModelForm):
    class Meta:
        model = Credor
        fields = [
            'tipo', 'cpf_cnpj', 'nome',
            'telefone', 'email',
            'conta', 'chave_pix',  'grupo',
            'cargo_funcao'
        ]
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'cpf_cnpj': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apenas números'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'grupo': forms.Select(attrs={'class': 'form-select'}),
            'cargo_funcao': forms.Select(attrs={'class': 'form-select'}),
            'conta': forms.Select(attrs={'class': 'form-select'}),
            'chave_pix': forms.TextInput(attrs={'class': 'form-control'}),
        }

# ==========================================
# 1. FORMULÁRIO DE DIÁRIAS
# ==========================================
class DiariaForm(forms.ModelForm):
    class Meta:
        model = Diaria
        fields = [
            'numero_sequencial', 'processo', 'status', 'beneficiario',
            'tipo_solicitacao', 'data_saida', 'data_retorno',
            'cidade_origem', 'cidade_destino', 'objetivo',
            'quantidade_diarias', 'valor_total'
        ]
        widgets = {
            'numero_sequencial': forms.TextInput(attrs={'class': 'form-control'}),
            'processo': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'beneficiario': forms.Select(attrs={'class': 'form-select'}),
            'tipo_solicitacao': forms.Select(attrs={'class': 'form-select'}),
            # O type="date" invoca o calendário nativo do navegador
            'data_saida': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_retorno': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'cidade_origem': forms.TextInput(attrs={'class': 'form-control'}),
            'cidade_destino': forms.TextInput(attrs={'class': 'form-control'}),
            'objetivo': forms.TextInput(attrs={'class': 'form-control'}),
            'quantidade_diarias': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

# ==========================================
# 2. FORMULÁRIO DE REEMBOLSO DE COMBUSTÍVEL
# ==========================================
class ReembolsoForm(forms.ModelForm):
    class Meta:
        model = ReembolsoCombustivel
        fields = [
            'numero_sequencial', 'processo', 'status', 'beneficiario',
            'data_saida', 'data_retorno', 'cidade_origem', 'cidade_destino',
            'distancia_km', 'preco_combustivel', 'objetivo', 'valor_total'
        ]
        widgets = {
            'numero_sequencial': forms.TextInput(attrs={'class': 'form-control'}),
            'processo': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
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

# ==========================================
# 3. FORMULÁRIO DE JETON
# ==========================================
class JetonForm(forms.ModelForm):
    class Meta:
        model = Jeton
        fields = [
            'numero_sequencial', 'processo', 'status', 'beneficiario',
            'reuniao', 'valor_total'
        ]
        widgets = {
            'numero_sequencial': forms.TextInput(attrs={'class': 'form-control'}),
            'processo': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'beneficiario': forms.Select(attrs={'class': 'form-select'}),
            'reuniao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Março/2026 ou 15ª Sessão'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

# ==========================================
# 4. FORMULÁRIO DE AUXÍLIO REPRESENTAÇÃO
# ==========================================
class AuxilioForm(forms.ModelForm):
    class Meta:
        model = AuxilioRepresentacao
        fields = [
            'numero_sequencial', 'processo', 'status', 'beneficiario',
            'objetivo', 'valor_total'
        ]
        widgets = {
            'numero_sequencial': forms.TextInput(attrs={'class': 'form-control'}),
            'processo': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'beneficiario': forms.Select(attrs={'class': 'form-select'}),
            'objetivo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Motivo ou evento da representação'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }