from django.db import models
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from simple_history.models import HistoricalRecords

from .fluxo import DocumentoBase, caminho_documento, _delete_file
from processos.validators import validar_arquivo_seguro


class StatusChoicesSuprimentoDeFundos(models.Model):
    # This replaces your hard-coded choices
    status_choice = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.status_choice}"


class SuprimentoDeFundos(models.Model):
    processo = models.ForeignKey('Processo', on_delete=models.CASCADE, related_name='suprimentos', null=True,
                                 blank=True)
    suprido = models.ForeignKey('Credor', on_delete=models.PROTECT, limit_choices_to={'tipo': 'PF'},
                                verbose_name="Suprido")

    # Valores Iniciais
    valor_liquido = models.DecimalField("Valor do Numerário Liberado (R$)", max_digits=10, decimal_places=2)
    taxa_saque = models.DecimalField("Valor da Taxa de Saque (R$)", max_digits=5, decimal_places=2, default=0.00)

    # Período
    lotacao = models.CharField("Lotação", max_length=200, blank=True, null=True)
    data_saida = models.DateField("Período Inicial (De)")
    data_retorno = models.DateField("Período Final (Ate)")
    data_recibo = models.DateField("Data de Carga na Conta", blank=True, null=True)

    # Fechamento (Preenchido ao encerrar o mês)
    data_devolucao_saldo = models.DateField("Data de Devolução de Saldo Remanescente", blank=True, null=True)
    valor_devolvido = models.DecimalField("Valor Devolvido (R$)", max_digits=10, decimal_places=2, blank=True,
                                          null=True)

    status = models.ForeignKey('StatusChoicesSuprimentoDeFundos', on_delete=models.PROTECT, blank=True, null=True)

    # --- MÁGICA: Propriedades Calculadas Dinamicamente ---
    @property
    def valor_gasto(self):
        # Soma todas as despesas atreladas a este suprimento
        total = sum(despesa.valor for despesa in self.despesas.all())
        return total

    @property
    def saldo_remanescente(self):
        # Calcula quanto sobrou do dinheiro liberado
        return self.valor_liquido - self.valor_gasto

    def __str__(self):
        return f"Suprimento: {self.suprido} - Valor: R$ {self.valor_liquido}"
    history = HistoricalRecords()


class DespesaSuprimento(models.Model):
    suprimento = models.ForeignKey('SuprimentoDeFundos', on_delete=models.CASCADE, related_name='despesas')
    data = models.DateField("Data da Compra")
    estabelecimento = models.CharField("Estabelecimento (Credor)", max_length=150)
    cnpj_cpf = models.CharField("CNPJ/CPF", max_length=20, blank=True, null=True)
    detalhamento = models.CharField("Material/Serviço Adquirido", max_length=255)
    nota_fiscal = models.CharField("Nº Nota Fiscal/Cupom", max_length=50)
    valor = models.DecimalField("Valor Pago (R$)", max_digits=10, decimal_places=2)

    # NOVO CAMPO: O arquivo único contendo Solicitação + Nota Fiscal
    arquivo = models.FileField("Arquivo Único (Solicitação + NF)", upload_to=caminho_documento, blank=True, null=True, validators=[validar_arquivo_seguro])

    def __str__(self):
        return f"{self.data} - {self.estabelecimento} - R$ {self.valor}"
    history = HistoricalRecords()


class DocumentoSuprimentoDeFundos(DocumentoBase):
    suprimento = models.ForeignKey('SuprimentoDeFundos', on_delete=models.CASCADE, related_name='documentos')
    history = HistoricalRecords()


# ==============================================================================
# FILE LIFECYCLE SIGNALS – suprimento documents
# ==============================================================================

@receiver(post_delete, sender=DespesaSuprimento)
def auto_delete_file_on_delete_despesasuprimento(sender, instance, **kwargs):
    _delete_file(instance.arquivo)


@receiver(pre_save, sender=DespesaSuprimento)
def cleanup_old_file_on_save_despesasuprimento(sender, instance, **kwargs):
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
    _delete_file(instance.arquivo)


@receiver(pre_save, sender=DocumentoSuprimentoDeFundos)
def cleanup_old_file_on_save_docsuprimento(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    if old.arquivo and old.arquivo.name and old.arquivo.name != instance.arquivo.name:
        _delete_file(old.arquivo)
