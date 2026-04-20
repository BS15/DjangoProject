"""Modelos auxiliares de auditoria, contingência e registros do fluxo."""

from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from simple_history.models import HistoricalRecords

from commons.shared.file_validators import validar_arquivo_seguro


STATUS_CONTINGENCIA = [
    ("PENDENTE_SUPERVISOR", "Pendente Supervisor"),
    ("PENDENTE_ORDENADOR", "Pendente Ordenador de Despesa"),
    ("PENDENTE_CONSELHO", "Pendente Conselho Fiscal"),
    ("PENDENTE_CONTADOR", "Pendente Revisão da Contadora"),
    ("APROVADA", "Aprovada"),
    ("REJEITADA", "Rejeitada"),
]



class PendenciaProcessual(models.Model):
    """Pendência operacional ou documental atrelada ao processo."""
    processo = models.ForeignKey("pagamentos.Processo", on_delete=models.CASCADE, related_name="pendencias")
    status = models.ForeignKey("pagamentos.StatusOpcoesPendencia", on_delete=models.PROTECT, blank=True, null=True)
    tipo = models.ForeignKey("pagamentos.TiposPendencia", on_delete=models.PROTECT)
    descricao = models.CharField(max_length=200, blank=True, null=True)
    history = HistoricalRecords()
    def __str__(self):
        return f"PENDÊNCIA: {self.tipo} - {self.descricao}"



class ContingenciaProcessual(models.Model):
    """Solicitação formal de retificação com trilha de aprovação multi-etapa."""
    processo = models.ForeignKey("pagamentos.Processo", on_delete=models.CASCADE, related_name="contingencias")
    solicitante = models.ForeignKey(User, on_delete=models.PROTECT, related_name="contingencias_solicitadas")
    data_solicitacao = models.DateTimeField(auto_now_add=True)
    justificativa = models.TextField(help_text="Motivo detalhado para a quebra de fluxo/retificação.")
    dados_propostos = models.JSONField(
        default=dict,
        help_text="Dicionário JSON contendo o estado exato dos campos que serão alterados no Processo (ex: {'credor_id': 5}).",
    )
    status = models.CharField(max_length=30, choices=STATUS_CONTINGENCIA, default="PENDENTE_SUPERVISOR")
    exige_aprovacao_ordenador = models.BooleanField(default=False)
    exige_aprovacao_conselho = models.BooleanField(default=False)
    exige_revisao_contadora = models.BooleanField(default=True)
    parecer_supervisor = models.TextField(blank=True, null=True)
    aprovado_por_supervisor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="cont_supervisionadas",
        null=True,
        blank=True,
    )
    data_aprovacao_supervisor = models.DateTimeField(null=True, blank=True)
    parecer_ordenador = models.TextField(blank=True, null=True)
    aprovado_por_ordenador = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="cont_ordenadas",
        null=True,
        blank=True,
    )
    data_aprovacao_ordenador = models.DateTimeField(null=True, blank=True)
    parecer_conselho = models.TextField(blank=True, null=True)
    aprovado_por_conselho = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="cont_conselho",
        null=True,
        blank=True,
    )
    data_aprovacao_conselho = models.DateTimeField(null=True, blank=True)
    parecer_contadora = models.TextField(blank=True, null=True)
    revisado_por_contadora = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="cont_revisadas_contadora",
        null=True,
        blank=True,
    )
    data_revisao_contadora = models.DateTimeField(null=True, blank=True)
    history = HistoricalRecords()
    class Meta:
        verbose_name = "Contingência"
        verbose_name_plural = "Contingências"
        ordering = ["-data_solicitacao"]
    def __str__(self):
        return f"Contingência #{self.pk} - Processo {self.processo} [{self.get_status_display()}]"



class RegistroAcessoArquivoProcessual(models.Model):
    """Log de acesso a arquivos para auditoria e rastreabilidade."""
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, null=True)
    nome_arquivo = models.CharField(max_length=500)
    data_acesso = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    history = HistoricalRecords()
    class Meta:
        verbose_name = "Registro de Acesso a Arquivo"
        verbose_name_plural = "Registros de Acesso a Arquivos"
        ordering = ["-data_acesso"]
    def __str__(self):
        return f"{self.usuario} acessou {self.nome_arquivo}"



class DevolucaoProcessual(models.Model):
    """Registro de devolução de valores relacionados ao processo."""
    processo = models.ForeignKey("pagamentos.Processo", on_delete=models.CASCADE, related_name="devolucoes")
    valor_devolvido = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0.01)])
    data_devolucao = models.DateField()
    motivo = models.TextField()
    comprovante = models.FileField(
        upload_to="devolucoes/",
        validators=[validar_arquivo_seguro],
        help_text="Comprovante de depósito/GRU",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()
    class Meta:
        verbose_name = "Devolução"
        verbose_name_plural = "Devoluções"
        ordering = ["-data_devolucao"]
    def clean(self):
        """Valida que devolução não excede valor líquido do processo."""
        if self.processo_id:
            total_devolvido = self.processo.devolucoes.exclude(pk=self.pk).aggregate(t=Sum("valor_devolvido"))["t"] or 0
            total_com_esta = total_devolvido + self.valor_devolvido
            if total_com_esta > self.processo.valor_liquido:
                raise ValidationError(
                    f"Total de devoluções ({total_com_esta}) não pode exceder valor líquido ({self.processo.valor_liquido})."
                )
    def __str__(self):
        return f"Devolução de R$ {self.valor_devolvido} - Processo {self.processo}"



class AssinaturaEletronica(models.Model):
    """Metadados de integração com assinatura eletrônica via Autentique."""
    STATUS_CHOICES = [
        ("RASCUNHO", "Rascunho"),
        ("PENDENTE", "Pendente"),
        ("ASSINADO", "Assinado"),
        ("REJEITADO", "Rejeitado"),
        ("ERRO", "Erro"),
    ]
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    entidade_relacionada = GenericForeignKey("content_type", "object_id")
    criador = models.ForeignKey(User, on_delete=models.PROTECT, related_name="assinaturas_criadas")
    tipo_documento = models.CharField("Tipo do Documento", max_length=50, help_text="Ex: SCD, PCD, AUTORIZACAO")
    autentique_id = models.CharField("ID Autentique", max_length=100, unique=True, null=True, blank=True)
    autentique_url = models.URLField("URL para Assinatura", max_length=500, blank=True, default="")
    dados_signatarios = models.JSONField("Dados dos Signatários", default=dict, blank=True, null=True)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default="RASCUNHO")
    arquivo = models.FileField("Arquivo (Rascunho)", upload_to="assinaturas_rascunho/", null=True, blank=True)
    arquivo_assinado = models.FileField("Arquivo Assinado", upload_to="documentos_assinados/", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()
    class Meta:
        ordering = ["-criado_em"]
    def __str__(self):
        return f"{self.tipo_documento} - {self.autentique_id} ({self.status})"
