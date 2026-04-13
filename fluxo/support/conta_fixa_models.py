import datetime
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from credores.models import Credor

class ContaFixa(models.Model):
    """Configuração de despesa recorrente que gera faturas mensais."""
    credor = models.ForeignKey(
        Credor,
        on_delete=models.PROTECT,
        verbose_name="Credor/Fornecedor"
    )
    referencia = models.CharField(
        "Referência / Descrição",
        max_length=200,
        help_text="Ex: Conta de Luz - Sede"
    )
    dia_vencimento = models.IntegerField(
        "Dia Padrão de Vencimento",
        validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    ativa = models.BooleanField("Conta Ativa", default=True)
    data_inicio = models.DateField(
        "Data de Início",
        default=datetime.date.today,
        help_text="Mês a partir do qual as faturas mensais serão geradas."
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Conta Fixa"
        verbose_name_plural = "Contas Fixas"

    def __str__(self):
        return f"{self.credor.nome} - {self.referencia}"

class FaturaMensal(models.Model):
    """Fatura de referência mensal derivada de uma conta fixa."""
    conta_fixa = models.ForeignKey(
        ContaFixa,
        on_delete=models.CASCADE,
        related_name='faturas'
    )
    mes_referencia = models.DateField("Mês de Referência")
    processo_vinculado = models.ForeignKey(
        'fluxo.Processo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='faturas_vinculadas'
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Fatura Mensal"
        verbose_name_plural = "Faturas Mensais"
        unique_together = ('conta_fixa', 'mes_referencia')

    def __str__(self):
        return f"{self.conta_fixa} - {self.mes_referencia.strftime('%m/%Y')}"

    @property
    def data_vencimento_exata(self):
        """Calcula a data de vencimento respeitando o último dia do mês."""
        import calendar
        dia = self.conta_fixa.dia_vencimento
        ultimo_dia = calendar.monthrange(self.mes_referencia.year, self.mes_referencia.month)[1]
        dia_efetivo = min(dia, ultimo_dia)
        return self.mes_referencia.replace(day=dia_efetivo)

    @property
    def status(self):
        """Retorna estado operacional da fatura: pendente, em andamento ou pago."""
        if not self.processo_vinculado:
            return 'PENDENTE'
        if self.processo_vinculado.status and 'PAGO' in self.processo_vinculado.status.status_choice.upper():
            return 'PAGO'
        return 'EM ANDAMENTO'
