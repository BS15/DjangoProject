"""Modelos de comprovantes de pagamento e funções auxiliares para pagamentos no fluxo."""

from django.db import models
from django.core.validators import MinValueValidator
from simple_history.models import HistoricalRecords
from datetime import date
from commons.shared.file_validators import validar_arquivo_seguro


def caminho_comprovante(instance, filename):
    """Monta caminho de upload para comprovantes com fallback seguro."""
    if instance.processo_id:
        try:
            processo = instance.processo
            ano = processo.data_empenho.year if processo.data_empenho else date.today().year
            mes = processo.data_empenho.month if processo.data_empenho else date.today().month
            return f'pagamentos/{ano}/{mes:02d}/proc_{processo.id}/comprovantes/{filename}'
        except AttributeError as exc:
            # logger.warning(
            #     "Falha ao calcular caminho de comprovante para processo %s: %s",
            #     getattr(instance, "processo_id", None),
            #     exc,
            # )
            pass
    return f'comprovantes/{filename}'


class ComprovanteDePagamento(models.Model):
    """Comprovante bancário anexado para lastrear pagamento do processo."""

    processo = models.ForeignKey(
        'fluxo.Processo',
        on_delete=models.CASCADE,
        related_name='comprovantes_pagamento',
        verbose_name="Processo"
    )
    numero_comprovante = models.CharField(
        "Número do Comprovante",
        max_length=100,
        null=True,
        blank=True
    )
    credor_nome = models.CharField(
        "Credor (Texto)",
        max_length=200,
        null=True,
        blank=True
    )
    valor_pago = models.DecimalField(
        "Valor Pago",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    data_pagamento = models.DateField("Data de Pagamento", null=True, blank=True)
    arquivo = models.FileField(
        "Arquivo do Comprovante",
        upload_to=caminho_comprovante,
        null=True,
        blank=True,
        validators=[validar_arquivo_seguro]
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Comprovante de Pagamento"
        verbose_name_plural = "Comprovantes de Pagamento"

    def __str__(self):
        return f"Comprovante - {self.processo} - {self.credor_nome} - R$ {self.valor_pago}"
