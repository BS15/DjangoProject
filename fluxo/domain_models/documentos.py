"""Modelos documentais do processo e regras de ciclo de vida de arquivos."""

"""Modelos de documentos vinculados a processos do fluxo financeiro.

Este módulo define modelos para documentos orçamentários, de pagamento e de processo, com regras de ordenação e exibição.
"""

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import post_delete, pre_delete, pre_save
from django.dispatch import receiver
from simple_history.models import HistoricalRecords

from commons.shared.file_validators import validar_arquivo_seguro
from commons.shared.models import DocumentoBase
from commons.shared.storage_utils import _delete_file, caminho_documento


class Boleto_Bancario(DocumentoBase):
    """Documento anexado ao processo com controle de imutabilidade."""

    processo = models.ForeignKey("fluxo.Processo", on_delete=models.CASCADE, related_name="documentos")
    codigo_barras = models.CharField("Código de Barras", max_length=60, null=True, blank=True)
    imutavel = models.BooleanField(
        "Imutável",
        default=False,
        help_text="Documento bloqueado para exclusão. Definido automaticamente durante a etapa de Conferência.",
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Boleto_Bancario"
        verbose_name_plural = "Boleto_Bancario"


class DocumentoOrcamentario(DocumentoBase):
    """Documento orçamentário vinculado ao processo."""

    processo = models.ForeignKey("fluxo.Processo", on_delete=models.CASCADE, related_name="documentos_orcamentarios")
    numero_nota_empenho = models.CharField(max_length=50, blank=True, null=True)
    data_empenho = models.DateField(blank=True, null=True)
    ano_exercicio = models.IntegerField(
        choices=[(year, year) for year in range(2020, 2035)],
        blank=True,
        null=True,
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ["-data_empenho", "-id"]

    def __str__(self):
        numero = self.numero_nota_empenho or "S/N"
        ano = self.ano_exercicio or "----"
        return f"{numero} ({ano})"


class ComprovanteDePagamento(DocumentoBase):
    """Comprovante bancário anexado para lastrear pagamento do processo."""

    processo = models.ForeignKey(
        "fluxo.Processo",
        on_delete=models.CASCADE,
        related_name="comprovantes_pagamento",
        verbose_name="Processo",
    )
    numero_comprovante = models.CharField("Número do Comprovante", max_length=100, null=True, blank=True)
    credor_nome = models.CharField("Credor (Texto)", max_length=200, null=True, blank=True)
    valor_pago = models.DecimalField(
        "Valor Pago",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    data_pagamento = models.DateField("Data de Pagamento", null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Comprovante de Pagamento"
        verbose_name_plural = "Comprovantes de Pagamento"

    def __str__(self):
        return f"Comprovante - {self.processo} - {self.credor_nome} - R$ {self.valor_pago}"


@receiver(post_delete, sender=Boleto_Bancario)
def auto_delete_file_on_delete_boleto_bancario(sender, instance, **kwargs):
    """Remove arquivo físico quando Boleto_Bancario é excluído."""
    _delete_file(instance.arquivo)


@receiver(pre_save, sender=Boleto_Bancario)
def enforce_immutability_and_cleanup_on_save(sender, instance, **kwargs):
    """Bloqueia troca de arquivo em documento imutável e limpa versão anterior."""
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.imutavel and instance.arquivo.name != old.arquivo.name:
        raise ValidationError("Este documento é imutável e não pode ter seu arquivo substituído.")

    if old.arquivo and old.arquivo.name and old.arquivo.name != instance.arquivo.name:
        _delete_file(old.arquivo)


@receiver(pre_delete, sender=Boleto_Bancario)
def prevent_immutable_delete(sender, instance, **kwargs):
    """Impede exclusão de documentos marcados como imutáveis."""
    if instance.imutavel:
        raise ValidationError("Este documento é imutável e não pode ser excluído.")
