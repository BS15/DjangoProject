# --- MIGRADO DE credores.models ---
class DadosContribuinte(models.Model):
    """Identificação fiscal do órgão para filtros e integrações tributárias."""

    cnpj = models.CharField(max_length=14, validators=[validar_cpf_cnpj])
    razao_social = models.CharField(max_length=255)
    tipo_inscricao = models.IntegerField(default=1)
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.razao_social} ({self.cnpj})"

    class Meta:
        verbose_name = "Dados do Contribuinte"
        verbose_name_plural = "Dados do Contribuinte"
class Meta:
    permissions = [
        ("acesso_backoffice", "Acesso ao backoffice fiscal"),
    ]
"""Modelos fiscais: notas, retenções e integrações fiscais.

Este módulo define modelos para controle de notas fiscais, retenções de impostos e integrações fiscais.
"""

import logging
import re
from django.db import models
from datetime import date
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from simple_history.models import HistoricalRecords

from commons.shared.file_validators import validar_arquivo_seguro


logger = logging.getLogger(__name__)


def validar_cpf_cnpj(value):
    """Valida formato básico de CPF/CNPJ (apenas dígitos e separadores)."""
    if not value:
        return
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



# ComprovanteDePagamento and caminho_comprovante moved to fluxo.domain_models.comprovantes


class CodigosImposto(models.Model):
    """Tabela de códigos tributários e metadados de competência/Reinf."""

    codigo = models.CharField(max_length=10, unique=True, null=True, blank=True)

    REGRA_COMPETENCIA_CHOICES = [
        ('emissao', 'Pela Data de Emissão da NF'),
        ('pagamento', 'Pela Data de Pagamento'),
    ]
    regra_competencia = models.CharField(
        max_length=15,
        choices=REGRA_COMPETENCIA_CHOICES,
        default='emissao'
    )

    aliquota = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    natureza_rendimento = models.CharField(
        max_length=5,
        blank=True,
        null=True,
        verbose_name="Natureza do Rendimento (EFD-Reinf)",
        help_text="Código de 5 dígitos (Tabela 01 do SPED). Ex: 15001, 17001. Mapeia o código de receita para o XML."
    )

    SERIE_REINF_CHOICES = [
        ('NONE', 'Não mapeado'),
        ('S2000', 'Série 2000 – Previdenciário (INSS)'),
        ('S4000', 'Série 4000 – Retenções Federais (IRRF/CSRF)'),
    ]
    serie_reinf = models.CharField(
        max_length=6,
        choices=SERIE_REINF_CHOICES,
        default='NONE',
        verbose_name="Série EFD-Reinf",
        help_text="Classifica o imposto para geração do XML EFD-Reinf: S2000 = INSS, S4000 = IR/CSLL/PIS/COFINS."
    )

    def __str__(self):
        return f"{self.codigo}"


class StatusChoicesRetencoes(models.Model):
    """Catálogo de status aplicáveis às retenções de imposto."""

    status_choice = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.status_choice}"


class DocumentoFiscal(models.Model):
    """Nota fiscal vinculada ao processo com dados para ateste e retenção."""

    processo = models.ForeignKey('fluxo.Processo', on_delete=models.CASCADE, related_name='notas_fiscais')
    nome_emitente = models.ForeignKey('credores.Credor', on_delete=models.PROTECT, blank=True, null=True)
    cnpj_emitente = models.CharField(max_length=20, blank=False, validators=[validar_cpf_cnpj])
    numero_nota_fiscal = models.CharField(max_length=50)
    documento_vinculado = models.OneToOneField(
        'fluxo.DocumentoDePagamento',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='nota_referente',
        verbose_name="Documento PDF da Nota"
    )
    data_emissao = models.DateField()
    valor_bruto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    valor_liquido = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    fiscal_contrato = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        verbose_name="Fiscal do Contrato",
        related_name='notas_fiscalizadas',
        null=True,
        blank=True,
    )
    atestada = models.BooleanField(default=False)
    serie_nota_fiscal = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Série"
    )
    codigo_servico_inss = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name="Cód. Serviço INSS (Tabela 06 Reinf)"
    )
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['processo', 'numero_nota_fiscal', 'serie_nota_fiscal'],
                name='unique_nf_por_processo',
                condition=models.Q(serie_nota_fiscal__isnull=False)
            ),
        ]

    def save(self, *args, **kwargs):
        """Sincroniza CNPJ e herda código de serviço padrão do emitente."""
        if self.nome_emitente:
            self.cnpj_emitente = self.nome_emitente.cpf_cnpj
        if not self.codigo_servico_inss and self.nome_emitente and self.nome_emitente.codigo_servico_padrao:
            self.codigo_servico_inss = self.nome_emitente.codigo_servico_padrao
        super().save(*args, **kwargs)

    def clean(self):
        """Valida integridade dos dados da nota antes de salvar."""
        from django.core.exceptions import ValidationError as DjangoValidationError
        errors = {}
        if self.valor_liquido and self.valor_bruto:
            if self.valor_liquido > self.valor_bruto:
                errors['valor_liquido'] = 'Valor líquido não pode ser maior que o valor bruto.'
        
        if errors:
            raise DjangoValidationError(errors)

    def __str__(self):
        return f"NF {self.numero_nota_fiscal} - {self.nome_emitente}"


class RetencaoImposto(models.Model):
    """Imposto retido em nota fiscal com cálculo automático de competência."""

    nota_fiscal = models.ForeignKey('DocumentoFiscal', on_delete=models.CASCADE, related_name='retencoes')
    beneficiario = models.ForeignKey('credores.Credor', on_delete=models.PROTECT, blank=True, null=True, verbose_name="Beneficiário", related_name='retencoes')
    rendimento_tributavel = models.DecimalField("Base de Cálculo / Rend. Tributável", null=True, blank=True, max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    data_pagamento = models.DateField(blank=True, null=True)
    codigo = models.ForeignKey('CodigosImposto', on_delete=models.PROTECT)
    valor = models.DecimalField("Valor Retido", max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.ForeignKey('StatusChoicesRetencoes', on_delete=models.PROTECT, blank=True, null=True)
    processo_pagamento = models.ForeignKey(
        'fluxo.Processo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='impostos_recolhidos',
        verbose_name="Processo de Recolhimento",
        help_text="O Processo agrupado gerado para pagar esta retenção ao órgão arrecadador."
    )

    competencia = models.DateField(
        "Mês de Competência",
        help_text="Salvo internamente como YYYY-MM-01, exibido como MM/AAAA",
        blank=True,
        null=True
    )

    def save(self, *args, **kwargs):
        """Define competência mensal conforme regra do código e datas disponíveis."""
        if getattr(self, 'codigo', None) and getattr(self, 'nota_fiscal', None):
            data_base = None
            if self.codigo.regra_competencia == 'emissao':
                data_base = self.nota_fiscal.data_emissao

            elif self.codigo.regra_competencia == 'pagamento':
                data_base = self.data_pagamento or self.nota_fiscal.processo.data_pagamento
            if data_base:
                self.competencia = date(data_base.year, data_base.month, 1)
        super().save(*args, **kwargs)

    history = HistoricalRecords()

    def __str__(self):
        return f"{self.codigo} - R$ {self.valor}"


# ComprovanteDePagamento model moved to fluxo.domain_models.comprovantes
