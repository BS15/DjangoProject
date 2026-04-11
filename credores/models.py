"""Modelos cadastrais: credores, contas bancárias e contas fixas mensais."""

import datetime
import re
from django.core.validators import MaxValueValidator, MinValueValidator, EmailValidator
from django.db import models
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords


def validar_cpf_cnpj(value):
    """Valida formato básico de CPF/CNPJ (apenas dígitos e separadores)."""
    clean = re.sub(r'[\.\-\/]', '', value)
    if not re.match(r'^\d{11}(\d{2})?$', clean):
        raise ValidationError(
            'CPF deve ter 11 dígitos e CNPJ deve ter 13 dígitos.',
            code='invalid_cpf_cnpj'
        )

    if len(clean) == 11:
        if clean == clean[0] * 11:
            raise ValidationError('CPF inválido (dígitos repetidos).', code='invalid_cpf')

    elif len(clean) == 14:
        if clean == clean[0] * 14:
            raise ValidationError('CNPJ inválido (dígitos repetidos).', code='invalid_cnpj')


class CargosFuncoes(models.Model):
    """Catálogo de grupos e cargos/funções para classificação de credores."""

    grupo = models.CharField(max_length=100, verbose_name="Grupo Relacionado", blank=True, default='')
    cargo_funcao = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    history = HistoricalRecords()

    class Meta:
        unique_together = ('grupo', 'cargo_funcao')
        verbose_name = "Cargo / Função"
        verbose_name_plural = "Cargos e Funções"

    def __str__(self):
        return f"{self.grupo} -> {self.cargo_funcao}"


class ContasBancarias(models.Model):
    """Conta bancária vinculável ao credor para pagamento e conciliação."""

    titular = models.ForeignKey('Credor', on_delete=models.CASCADE, null=True, blank=True, related_name='contas_bancarias')
    banco = models.CharField("Banco", max_length=50, blank=True, null=True)
    agencia = models.CharField("Agência", max_length=50, blank=True, null=True)
    conta = models.CharField("Conta", max_length=50, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"Titular: {self.titular} - Banco: {self.banco} - Ag: {self.agencia} / Cc: {self.conta}"


class Credor(models.Model):
    """Entidade favorecida em pagamentos, verbas e retenções."""

    nome = models.CharField("Nome", max_length=50, null=False, blank=False)
    cpf_cnpj = models.CharField("CPF/CNPJ", max_length=50, null=False, blank=False, validators=[validar_cpf_cnpj])
    conta = models.ForeignKey('ContasBancarias', on_delete=models.PROTECT, blank=True, null=True, verbose_name="Conta Credor")
    chave_pix = models.CharField("Chave PIX do credor", max_length=50, null=True, blank=True)
    cargo_funcao = models.ForeignKey('CargosFuncoes', on_delete=models.PROTECT, blank=True, null=True)
    telefone = models.CharField("Telefone do credor", max_length=20, null=True, blank=True)
    email = models.EmailField("Email do credor", max_length=254, null=True, blank=True)

    TIPO_PESSOA_CHOICES = [
        ('PF', 'Pessoa Física (CPF)'),
        ('PJ', 'Pessoa Jurídica (CNPJ)'),
        ('EX', 'Exterior / Outros'),
    ]

    tipo = models.CharField(
        "Tipo de Pessoa",
        max_length=2,
        choices=TIPO_PESSOA_CHOICES,
        default='PJ'
    )
    codigo_servico_padrao = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name="Cód. Serviço Padrão INSS (Tabela 06)",
        help_text="Ex: 100000001 (Limpeza). Será herdado automaticamente pelas Notas Fiscais deste credor."
    )
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.nome}"



# Modelo DadosContribuinte migrado para fiscal.models



# Modelos ContaFixa e FaturaMensal migrados para fluxo.support.conta_fixa_models
