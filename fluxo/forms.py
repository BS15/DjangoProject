"""Formulários de entrada e validação para o fluxo principal de processos."""

from django import forms
from django.forms import inlineformset_factory
from fluxo.domain_models import (
	Processo,
	Boleto_Bancario,
	DocumentoOrcamentario,
	Pendencia,
	Devolucao,
	StatusChoicesPendencias,
	TiposDePagamento,
)
from fiscal.models import DadosContribuinte
from credores.models import ContasBancarias, ContaFixa
from fluxo.validators import validar_regras_processo, STATUS_BLOQUEADOS_FORM

SUPRIMENTO_DE_FUNDOS = 'SUPRIMENTO DE FUNDOS'


class ProcessoForm(forms.ModelForm):
	"""Formulário principal de Processo com bloqueios por estágio e filtros de domínio."""

	n_nota_empenho = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
	data_empenho = forms.DateField(
		required=False,
		input_formats=['%Y-%m-%d'],
		widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
	)
	ano_exercicio = forms.ChoiceField(
		required=False,
		choices=[('', '---------')] + [(y, y) for y in range(2020, 2035)],
		widget=forms.Select(attrs={'class': 'form-select'}),
	)

	class Meta:
		model = Processo
		exclude = ['status']
		widgets = {
			'extraorcamentario': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
			'credor': forms.Select(attrs={'class': 'form-select'}),
			'conta': forms.Select(attrs={'class': 'form-select'}),
			'tipo_pagamento': forms.Select(attrs={'class': 'form-select'}),
			'forma_pagamento': forms.Select(attrs={'class': 'form-select'}),
			'data_pagamento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
			'data_vencimento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
			'valor_bruto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
			'valor_liquido': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
			'detalhamento': forms.TextInput(attrs={'class': 'form-control'}),
			'observacao': forms.TextInput(attrs={'class': 'form-control'}),
			'tag': forms.Select(attrs={'class': 'form-select'})
		}

	def __init__(self, *args, **kwargs):
		"""Configura obrigatoriedade, travas por status e querysets contextuais."""
		super().__init__(*args, **kwargs)

		campos_obrigatorios = [
			'credor', 'valor_bruto', 'valor_liquido',
			'data_vencimento', 'data_pagamento',
			'tipo_pagamento', 'forma_pagamento'
		]

		for field_name in self.fields:
			if field_name in campos_obrigatorios:
				self.fields[field_name].required = True
			else:
				self.fields[field_name].required = False

		self.status_bloqueados = STATUS_BLOQUEADOS_FORM

		if self.instance and self.instance.pk:
			self.fields['n_nota_empenho'].initial = self.instance.n_nota_empenho
			self.fields['data_empenho'].initial = self.instance.data_empenho
			self.fields['ano_exercicio'].initial = self.instance.ano_exercicio

		if self.instance and self.instance.pk and self.instance.status:
			status_atual = self.instance.status.status_choice.upper()

			if status_atual in self.status_bloqueados:

				for campo in ['valor_liquido', 'valor_bruto']:
					if campo in self.fields:
						self.fields[campo].widget.attrs['readonly'] = True
						self.fields[campo].widget.attrs['class'] = self.fields[campo].widget.attrs.get('class', '') + ' bg-light'

				if 'credor' in self.fields:
					self.fields['credor'].widget.attrs['disabled'] = 'disabled'
					self.fields['credor'].widget.attrs['class'] = self.fields['credor'].widget.attrs.get('class', '') + ' bg-light'
					self.fields['credor'].required = False

		qs = TiposDePagamento.objects.exclude(tipo_de_pagamento__iexact=SUPRIMENTO_DE_FUNDOS)
		if self.instance and self.instance.pk and self.instance.tipo_pagamento:
			if self.instance.tipo_pagamento.tipo_de_pagamento.upper() == SUPRIMENTO_DE_FUNDOS:
				qs = TiposDePagamento.objects.all()
		self.fields['tipo_pagamento'].queryset = qs

		contribuinte = DadosContribuinte.objects.first()
		if contribuinte:
			self.fields['conta'].queryset = ContasBancarias.objects.filter(
				titular__cpf_cnpj=contribuinte.cnpj
			)
		else:
			self.fields['conta'].queryset = ContasBancarias.objects.none()

	def clean_credor(self):
		"""Preserva o credor original quando o processo está em estágio bloqueado."""
		credor_enviado = self.cleaned_data.get('credor')
		if self.instance and self.instance.pk and self.instance.status:
			if self.instance.status.status_choice.upper() in getattr(self, 'status_bloqueados', []):
				return self.instance.credor
		return credor_enviado

	def clean_valor_liquido(self):
		"""Evita alteração de valor líquido em estágios bloqueados."""
		valor_enviado = self.cleaned_data.get('valor_liquido')
		if self.instance and self.instance.pk and self.instance.status:
			if self.instance.status.status_choice.upper() in getattr(self, 'status_bloqueados', []):
				return self.instance.valor_liquido
		return valor_enviado

	def clean_valor_bruto(self):
		"""Evita alteração de valor bruto em estágios bloqueados."""
		valor_enviado = self.cleaned_data.get('valor_bruto')
		if self.instance and self.instance.pk and self.instance.status:
			if self.instance.status.status_choice.upper() in getattr(self, 'status_bloqueados', []):
				return self.instance.valor_bruto
		return valor_enviado

	def clean(self):
		"""Aplica validações de negócio do processo e agrega erros no formulário."""
		cleaned_data = super().clean()
		erros_processo = validar_regras_processo(cleaned_data)
		if erros_processo:
			for field, error in erros_processo.items():
				self.add_error(field, error)
		return cleaned_data

	def save(self, commit=True):
		processo = super().save(commit=commit)

		n_nota_empenho = self.cleaned_data.get('n_nota_empenho')
		data_empenho = self.cleaned_data.get('data_empenho')
		ano_exercicio = self.cleaned_data.get('ano_exercicio')
		ano_exercicio = int(ano_exercicio) if ano_exercicio not in (None, '',) else None

		if commit and any(v not in (None, '') for v in (n_nota_empenho, data_empenho, ano_exercicio)):
			atual = processo.documento_orcamentario_principal
			mudou = (
				not atual
				or atual.numero_nota_empenho != n_nota_empenho
				or atual.data_empenho != data_empenho
				or atual.ano_exercicio != ano_exercicio
			)
			if mudou:
				processo.registrar_documento_orcamentario(
					numero_nota_empenho=n_nota_empenho,
					data_empenho=data_empenho,
					ano_exercicio=ano_exercicio,
				)

		return processo


DocumentoFormSet = inlineformset_factory(
	Processo,
	Boleto_Bancario,
	fields=['tipo', 'ordem', 'arquivo'],
	extra=1,
	can_delete=True,
	widgets={
		'tipo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
		'ordem': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'style': 'width: 60px'}),
		'arquivo': forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm'}),
	}
)

DocumentoOrcamentarioFormSet = inlineformset_factory(
	Processo,
	DocumentoOrcamentario,
	fields=['numero_nota_empenho', 'data_empenho', 'ano_exercicio'],
	extra=1,
	can_delete=False,
	widgets={
		'numero_nota_empenho': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
		'data_empenho': forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
		'ano_exercicio': forms.Select(attrs={'class': 'form-select form-select-sm'}),
	},
)


class PendenciaForm(forms.ModelForm):
	"""Formulário de pendência que injeta status padrão na criação."""

	class Meta:
		model = Pendencia
		fields = ['tipo', 'descricao']
		widgets = {
			'tipo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
			'descricao': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Descreva a pendência detalhadamente...'}),
		}

	def save(self, commit=True):
		"""Salva pendência e garante status inicial ``A RESOLVER`` quando ausente."""
		pendencia = super().save(commit=False)

		if not pendencia.status:
			status_obj, _ = StatusChoicesPendencias.objects.get_or_create(
				status_choice__iexact='A RESOLVER',
				defaults={'status_choice': 'A RESOLVER'}
			)
			pendencia.status = status_obj

		if commit:
			pendencia.save()
		return pendencia


PendenciaFormSet = inlineformset_factory(
	Processo, Pendencia,
	form=PendenciaForm,
	extra=1,
	can_delete=True
)


class DevolucaoForm(forms.ModelForm):
	"""Formulário para registrar devoluções vinculadas a um processo."""

	class Meta:
		model = Devolucao
		fields = ['valor_devolvido', 'data_devolucao', 'motivo', 'comprovante']
		widgets = {
			'valor_devolvido': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
			'data_devolucao': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
			'motivo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
			'comprovante': forms.ClearableFileInput(attrs={'class': 'form-control'}),
		}
