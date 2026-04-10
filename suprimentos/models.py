"""Modelos de suprimento de fundos, despesas e documentos associados."""

from django.db import models
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from simple_history.models import HistoricalRecords
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError as DjangoValidationError

from commons.shared.file_validators import validar_arquivo_seguro
from commons.shared.models import DocumentoBase
from commons.shared.storage_utils import caminho_documento, _delete_file


class StatusChoicesSuprimentoDeFundos(models.Model):
    """Catálogo de status para o ciclo de suprimento de fundos."""

    # This replaces your hard-coded choices
    status_choice = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.status_choice}"


class SuprimentoDeFundos(models.Model):
    """Concessão de suprimento com controle de saldo e prestação de contas."""

    processo = models.ForeignKey('fluxo.Processo', on_delete=models.CASCADE, related_name='suprimentos', null=True,
                                 blank=True)
    suprido = models.ForeignKey('credores.Credor', on_delete=models.PROTECT, limit_choices_to={'tipo': 'PF'},
                                verbose_name="Suprido")

    # Valores Iniciais
    valor_liquido = models.DecimalField("Valor do Numerário Liberado (R$)", max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    taxa_saque = models.DecimalField("Valor da Taxa de Saque (R$)", max_digits=5, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])

    # Período
    lotacao = models.CharField("Lotação", max_length=200, blank=True, null=True)
    data_saida = models.DateField("Período Inicial (De)")
    data_retorno = models.DateField("Período Final (Ate)")
    data_recibo = models.DateField("Data de Carga na Conta", blank=True, null=True)

    # Fechamento (Preenchido ao encerrar o mês)
    data_devolucao_saldo = models.DateField("Data de Devolução de Saldo Remanescente", blank=True, null=True)
    valor_devolvido = models.DecimalField("Valor Devolvido (R$)", max_digits=10, decimal_places=2, blank=True,
                                          null=True, validators=[MinValueValidator(0)])

    status = models.ForeignKey('StatusChoicesSuprimentoDeFundos', on_delete=models.PROTECT, blank=True, null=True)

    # --- MÁGICA: Propriedades Calculadas Dinamicamente ---
    @property
    def valor_gasto(self):
        """Soma o valor das despesas vinculadas ao suprimento."""
        # Soma todas as despesas atreladas a este suprimento
        total = sum(despesa.valor for despesa in self.despesas.all())
        return total

    @property
    def saldo_remanescente(self):
        """Calcula saldo remanescente entre valor liberado e gasto."""
        # Calcula quanto sobrou do dinheiro liberado
        return self.valor_liquido - self.valor_gasto

    def __str__(self):
        return f"Suprimento: {self.suprido} - Valor: R$ {self.valor_liquido}"
    history = HistoricalRecords()
    def clean(self):
        """Valida que data_retorno é posterior ou igual a data_saida."""
        errors = {}
        
        if self.data_retorno and self.data_saida:
            if self.data_retorno < self.data_saida:
                errors['data_retorno'] = 'Data de retorno não pode ser anterior à data de saída.'
        
        if self.data_devolucao_saldo and self.data_recibo:
            if self.data_devolucao_saldo < self.data_recibo:
                errors['data_devolucao_saldo'] = 'Data de devolução não pode ser anterior à data de carga na conta.'
        
        if errors:
            raise DjangoValidationError(errors)


class DespesaSuprimento(models.Model):
    """Despesa individual registrada dentro de um suprimento de fundos."""

    suprimento = models.ForeignKey('SuprimentoDeFundos', on_delete=models.CASCADE, related_name='despesas')
    data = models.DateField("Data da Compra")
    estabelecimento = models.CharField("Estabelecimento (Credor)", max_length=150)
    cnpj_cpf = models.CharField("CNPJ/CPF", max_length=20, blank=True, null=True)
    detalhamento = models.CharField("Material/Serviço Adquirido", max_length=255)
    nota_fiscal = models.CharField("Nº Nota Fiscal/Cupom", max_length=50)
    valor = models.DecimalField("Valor Pago (R$)", max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    # NOVO CAMPO: O arquivo único contendo Solicitação + Nota Fiscal
    arquivo = models.FileField("Arquivo Único (Solicitação + NF)", upload_to=caminho_documento, blank=True, null=True, validators=[validar_arquivo_seguro])

    def __str__(self):
        return f"{self.data} - {self.estabelecimento} - R$ {self.valor}"
    history = HistoricalRecords()


class DocumentoSuprimentoDeFundos(DocumentoBase):
    """Documento geral vinculado ao suprimento (fora das despesas)."""

    suprimento = models.ForeignKey('SuprimentoDeFundos', on_delete=models.CASCADE, related_name='documentos')
    history = HistoricalRecords()


# ==============================================================================
# FILE LIFECYCLE SIGNALS – suprimento documents
# ==============================================================================

@receiver(post_delete, sender=DespesaSuprimento)
def auto_delete_file_on_delete_despesasuprimento(sender, instance, **kwargs):
    """Remove arquivo físico ao excluir despesa de suprimento."""
    _delete_file(instance.arquivo)


@receiver(pre_save, sender=DespesaSuprimento)
def cleanup_old_file_on_save_despesasuprimento(sender, instance, **kwargs):
    """Apaga arquivo antigo ao substituir anexo da despesa."""
    if not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    if old.arquivo and old.arquivo.name and old.arquivo.name != instance.arquivo.name:
        _delete_file(old.arquivo)


@receiver(post_delete, sender=DocumentoSuprimentoDeFundos)
def auto_delete_file_on_delete_docsuprimento(sender, instance, **kwargs):
    """Remove arquivo físico ao excluir documento de suprimento."""
    _delete_file(instance.arquivo)


@receiver(pre_save, sender=DocumentoSuprimentoDeFundos)
def cleanup_old_file_on_save_docsuprimento(sender, instance, **kwargs):
    """Apaga arquivo antigo ao substituir anexo do documento de suprimento."""
    if not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    if old.arquivo and old.arquivo.name and old.arquivo.name != instance.arquivo.name:
        _delete_file(old.arquivo)
