"""Modelos de suprimento de fundos, despesas e documentos associados.

Este módulo define modelos para controle de suprimentos de fundos, despesas, documentos e ciclo de prestação de contas.
"""

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from simple_history.models import HistoricalRecords
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone

from commons.shared.file_validators import validar_arquivo_seguro
from commons.shared.models import DocumentoBase
from commons.shared.processo_guards import is_processo_selado as _is_processo_selado
from commons.shared.storage_utils import caminho_documento, _delete_file


class SealedMutationQuerySet(models.QuerySet):
    """Bloqueia mutações em massa que contornam save/clean do domínio."""

    def update(self, **kwargs):
        """Bloqueia update() em massa para proteger invariantes do domínio."""
        raise DjangoValidationError(
            "Mutações em massa via update() são proibidas neste domínio. "
            "Use métodos de entidade/serviço com validações de negócio."
        )

    def bulk_update(self, objs, fields, batch_size=None):
        """Bloqueia bulk_update() em massa para proteger invariantes do domínio."""
        raise DjangoValidationError(
            "Mutações em massa via bulk_update() são proibidas neste domínio. "
            "Use métodos de entidade/serviço com validações de negócio."
        )

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False, update_conflicts=False, update_fields=None, unique_fields=None):
        """Bloqueia bulk_create() em massa para proteger invariantes do domínio."""
        raise DjangoValidationError(
            "Inserções em massa via bulk_create() são proibidas neste domínio. "
            "Use criação canônica por entidade para garantir invariantes."
        )


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

    processo = models.ForeignKey('pagamentos.Processo', on_delete=models.CASCADE, related_name='suprimentos', null=True,
                                 blank=True)
    suprido = models.ForeignKey('credores.Credor', on_delete=models.PROTECT, limit_choices_to={'tipo': 'PF'},
                                verbose_name="Suprido")

    # Valores Iniciais
    valor_liquido = models.DecimalField("Valor do Numerário Liberado (R$)", max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    taxa_saque = models.DecimalField("Valor da Taxa de Saque (R$)", max_digits=5, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])

    # Período
    lotacao = models.CharField("Lotação", max_length=200, blank=True, null=True)
    inicio_periodo = models.DateField("Período Inicial (De)")
    fim_periodo = models.DateField("Período Final (Até)")
    data_recibo = models.DateField("Data de Carga na Conta", blank=True, null=True)

    # Fechamento (Preenchido ao encerrar o mês)
    data_devolucao_saldo = models.DateField("Data de Devolução de Saldo Remanescente", blank=True, null=True)
    valor_devolvido = models.DecimalField("Valor Devolvido (R$)", max_digits=10, decimal_places=2, blank=True,
                                          null=True, validators=[MinValueValidator(0)])

    status = models.ForeignKey('StatusChoicesSuprimentoDeFundos', on_delete=models.PROTECT, blank=True, null=True)
    _CAMPOS_SENSIVEIS_POS_PAGAMENTO = {
        "suprido_id",
        "valor_liquido",
        "taxa_saque",
        "lotacao",
        "inicio_periodo",
        "fim_periodo",
        "data_recibo",
        "data_devolucao_saldo",
        "valor_devolvido",
        "processo_id",
    }
    objects = SealedMutationQuerySet.as_manager()

    # --- MÁGICA: Propriedades Calculadas Dinamicamente ---
    @property
    def valor_gasto(self):
        """Soma o valor das despesas vinculadas ao suprimento."""
        total = sum(despesa.valor for despesa in self.despesas.all())
        return total

    @property
    def saldo_remanescente(self):
        """Calcula saldo remanescente entre valor liberado e gasto."""
        return self.valor_liquido - self.valor_gasto

    def __str__(self):
        return f"Suprimento: {self.suprido} - Valor: R$ {self.valor_liquido}"

    history = HistoricalRecords()

    def clean(self):
        """Valida que fim_periodo é posterior ou igual a inicio_periodo."""
        errors = {}
        
        if self.fim_periodo and self.inicio_periodo:
            if self.fim_periodo < self.inicio_periodo:
                errors['fim_periodo'] = 'Data final do período não pode ser anterior ao início.'
        
        if self.data_devolucao_saldo and self.data_recibo:
            if self.data_devolucao_saldo < self.data_recibo:
                errors['data_devolucao_saldo'] = 'Data de devolução não pode ser anterior à data de carga na conta.'
        
        if errors:
            raise DjangoValidationError(errors)

    def _enforce_domain_seal(self, update_fields=None):
        """Bloqueia alterações em campos sensíveis quando o processo está pós-pagamento."""
        if not self.pk or not _is_processo_selado(self.processo):
            return

        original = type(self).objects.get(pk=self.pk)
        campos_sensiveis = self._CAMPOS_SENSIVEIS_POS_PAGAMENTO
        campos_avaliados = set(update_fields) & campos_sensiveis if update_fields is not None else campos_sensiveis
        alterados = [campo for campo in campos_avaliados if getattr(self, campo) != getattr(original, campo)]

        if alterados:
            raise DjangoValidationError(
                {
                    "status": (
                        "Mutação direta bloqueada: suprimento vinculado a processo em estágio pós-pagamento. "
                        "Use fluxo de contingência aprovado para ajustes."
                    )
                }
            )

    def save(self, *args, **kwargs):
        """Aplica domain seal, valida e persiste o suprimento."""
        self._enforce_domain_seal(update_fields=kwargs.get("update_fields"))
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Bloqueia exclusão de suprimento vinculado a processo pós-pagamento."""
        self._enforce_domain_seal()
        return super().delete(*args, **kwargs)

    class Meta:
        permissions = [
            ("acesso_backoffice", "Acesso ao backoffice de suprimentos"),
            ("pode_gerenciar_concessao_suprimento", "Pode gerenciar concessão de suprimento de fundos"),
            ("pode_adicionar_despesas_suprimento", "Pode adicionar despesas de suprimento"),
            ("pode_encerrar_suprimento", "Pode encerrar suprimento"),
            ("pode_gerir_prestacao_contas_suprimento", "Pode gerir prestação de contas de suprimento"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fim_periodo__gte=models.F("inicio_periodo")),
                name="suprimento_periodo_valido_chk",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(data_devolucao_saldo__isnull=True)
                    | models.Q(data_recibo__isnull=True)
                    | models.Q(data_devolucao_saldo__gte=models.F("data_recibo"))
                ),
                name="suprimento_devolucao_gte_recibo_chk",
            ),
            models.CheckConstraint(
                condition=models.Q(valor_liquido__gte=0),
                name="suprimento_valor_liquido_nao_negativo_chk",
            ),
            models.CheckConstraint(
                condition=models.Q(taxa_saque__gte=0),
                name="suprimento_taxa_saque_nao_negativa_chk",
            ),
            models.CheckConstraint(
                condition=models.Q(valor_devolvido__isnull=True) | models.Q(valor_devolvido__gte=0),
                name="suprimento_valor_devolvido_nao_negativo_chk",
            ),
        ]


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
    objects = SealedMutationQuerySet.as_manager()

    def _enforce_domain_seal(self, update_fields=None):
        """Bloqueia alterações em campos sensíveis quando o processo está pós-pagamento."""
        if not self.pk:
            return

        processo = self.suprimento.processo if self.suprimento_id else None
        if not _is_processo_selado(processo):
            return

        original = type(self).objects.get(pk=self.pk)
        campos_sensiveis = {
            "suprimento_id",
            "data",
            "estabelecimento",
            "cnpj_cpf",
            "detalhamento",
            "nota_fiscal",
            "valor",
            "arquivo",
        }
        campos_avaliados = set(update_fields) & campos_sensiveis if update_fields is not None else campos_sensiveis
        alterados = [campo for campo in campos_avaliados if getattr(self, campo) != getattr(original, campo)]

        if alterados:
            raise DjangoValidationError(
                {
                    "status": (
                        "Mutação direta bloqueada: despesa vinculada a processo em estágio pós-pagamento. "
                        "Use fluxo de contingência aprovado para ajustes."
                    )
                }
            )

    def save(self, *args, **kwargs):
        """Aplica domain seal, valida e persiste a despesa."""
        self._enforce_domain_seal(update_fields=kwargs.get("update_fields"))
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Bloqueia exclusão de despesa vinculada a processo pós-pagamento."""
        self._enforce_domain_seal()
        return super().delete(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valor__gte=0),
                name="despesa_valor_nao_negativo_chk",
            ),
        ]


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


class PrestacaoContasSuprimento(models.Model):
    """Prestação de contas do suprimento de fundos com ciclo de submissão e revisão operacional."""

    STATUS_ABERTA = "ABERTA"
    STATUS_ENVIADA = "ENVIADA"
    STATUS_ENCERRADA = "ENCERRADA"
    STATUS_CHOICES = [
        (STATUS_ABERTA, "Aberta"),
        (STATUS_ENVIADA, "Aguardando Revisão"),
        (STATUS_ENCERRADA, "Encerrada"),
    ]

    suprimento = models.OneToOneField(
        'SuprimentoDeFundos',
        on_delete=models.PROTECT,
        related_name='prestacao_contas',
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ABERTA)

    # Campos preenchidos ao enviar a prestação
    comprovante_devolucao = models.FileField(
        "Comprovante de Devolução de Saldo",
        upload_to=caminho_documento,
        blank=True,
        null=True,
        validators=[validar_arquivo_seguro],
        help_text="Comprovante de depósito/GRU do saldo remanescente devolvido.",
    )
    data_devolucao = models.DateField("Data de Devolução do Saldo", blank=True, null=True)
    termo_fidedignidade_assinado = models.BooleanField(
        "Termo de fidedignidade assinado",
        default=False,
    )

    submetido_em = models.DateTimeField(null=True, blank=True)
    submetido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prestacoes_suprimento_submetidas',
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    encerrado_em = models.DateTimeField(null=True, blank=True)
    encerrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prestacoes_suprimento_encerradas',
    )

    history = HistoricalRecords()

    def __str__(self):
        return f"Prestação #{self.pk} - Suprimento #{self.suprimento_id} [{self.get_status_display()}]"


# ==============================================================================
# FILE LIFECYCLE SIGNALS – prestacao de contas suprimento
# ==============================================================================

@receiver(post_delete, sender=PrestacaoContasSuprimento)
def auto_delete_file_on_delete_prestacao_suprimento(sender, instance, **kwargs):
    """Remove comprovante físico ao excluir prestação de contas de suprimento."""
    _delete_file(instance.comprovante_devolucao)


@receiver(pre_save, sender=PrestacaoContasSuprimento)
def cleanup_old_file_on_save_prestacao_suprimento(sender, instance, **kwargs):
    """Apaga comprovante antigo ao substituir o arquivo da prestação."""
    if not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    old_file = old.comprovante_devolucao
    new_file = instance.comprovante_devolucao
    if old_file and old_file.name and old_file.name != (new_file.name if new_file else None):
        _delete_file(old_file)
