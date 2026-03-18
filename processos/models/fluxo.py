from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords
from datetime import date


# Substitua a sua função antiga por esta:
def caminho_documento(instance, filename):
    # 1. Processo Principal
    if hasattr(instance, 'processo') and instance.processo:
        ano = instance.processo.data_empenho.year if instance.processo.data_empenho else date.today().year
        mes = instance.processo.data_empenho.month if instance.processo.data_empenho else date.today().month
        return f'pagamentos/{ano}/{mes:02d}/proc_{instance.processo.id}/{filename}'

    # 2. Verbas Indenizatórias
    if hasattr(instance, 'diaria') and instance.diaria:
        return f'verbasindenizatorias/diarias/diaria_{instance.diaria.id}/{filename}'
    if hasattr(instance, 'reembolso') and instance.reembolso:
        return f'verbasindenizatorias/reembolsos/reembolso_{instance.reembolso.id}/{filename}'
    if hasattr(instance, 'jeton') and instance.jeton:
        return f'verbasindenizatorias/jetons/jeton_{instance.jeton.id}/{filename}'
    if hasattr(instance, 'auxilio') and instance.auxilio:
        return f'verbasindenizatorias/auxilios/auxilio_{instance.auxilio.id}/{filename}'

    # 3. Suprimentos de Fundos
    # A) Arquivos das Despesas (A Solicitação + Nota Fiscal unificada)
    if instance.__class__.__name__ == 'DespesaSuprimento':
        return f'suprimentosdefundos/suprimento_{instance.suprimento.id}/despesas/{filename}'

    # B) Arquivos Gerais do Suprimento Pai (Portarias, comprovante de depósito, etc)
    if hasattr(instance, 'suprimento') and instance.suprimento:
        return f'suprimentosdefundos/suprimento_{instance.suprimento.id}/{filename}'

    # 4. Fallback (Segurança)
    return f'documentos_avulsos/{filename}'


class StatusChoicesProcesso(models.Model):
    # This replaces your hard-coded choices
    status_choice = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.status_choice}"


class StatusChoicesPendencias(models.Model):
    # This replaces your hard-coded choices
    status_choice = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.status_choice}"


class TagChoices(models.Model):
    # This replaces your hard-coded choices
    tag_choice = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tag_choice}"


class FormasDePagamento(models.Model):
    # This replaces your hard-coded choices
    forma_de_pagamento = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.forma_de_pagamento}"


class TiposDePagamento(models.Model):
    # This replaces your hard-coded choices
    tipo_de_pagamento = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tipo_de_pagamento}"


class TiposDeDocumento(models.Model):
    # This replaces your hard-coded choices
    tipo_de_pagamento = models.ForeignKey('TiposDePagamento', on_delete=models.PROTECT, blank=True, null=True)
    tipo_de_documento = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tipo_de_documento}"


class TiposDePendencias(models.Model):
    # This replaces your hard-coded choices
    tipo_de_pendencia = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tipo_de_pendencia}"


class DocumentoBase(models.Model):
    arquivo = models.FileField(upload_to=caminho_documento)
    ordem = models.PositiveIntegerField(default=1, help_text="Ordem do arquivo")
    tipo = models.ForeignKey('TiposDeDocumento', on_delete=models.PROTECT)

    class Meta:
        abstract = True
        ordering = ['ordem']


STATUS_CONTINGENCIA = [
    ('PENDENTE_SUPERVISOR', 'Pendente Supervisor'),
    ('PENDENTE_ORDENADOR', 'Pendente Ordenador de Despesa'),
    ('PENDENTE_CONSELHO', 'Pendente Conselho Fiscal'),
    ('APROVADA', 'Aprovada'),
    ('REJEITADA', 'Rejeitada'),
]


class Processo(models.Model):
    # Dados orçamentários
    extraorcamentario = models.BooleanField(
        "Extraorçamentário",
        default=False,
        help_text="Marque se este processo não utiliza dotação orçamentária (ex: cauções)."
    )
    n_nota_empenho = models.CharField(max_length=50, blank=True, null=True)
    credor = models.ForeignKey('Credor', on_delete=models.PROTECT, blank=True, null=True)
    data_empenho = models.DateField(default=timezone.now, blank=True, null=True)
    valor_bruto = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, blank=True, null=True)
    valor_liquido = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, blank=True, null=True)
    ano_exercicio = models.IntegerField(choices=[(y, y) for y in range(2020, 2030)], default=2026, blank=True, null=True)

    # Dados de pagamento
    n_pagamento_siscac = models.CharField(max_length=50, blank=True, null=True)
    data_vencimento = models.DateField(blank=True, null=True)
    data_pagamento = models.DateField(blank=True, null=True)
    forma_pagamento = models.ForeignKey('FormasDePagamento', on_delete=models.PROTECT, blank=True, null=True)
    tipo_pagamento = models.ForeignKey('TiposDePagamento', on_delete=models.PROTECT, blank=True, null=True)
    observacao = models.CharField(max_length=200, blank=True, null=True)
    conta = models.ForeignKey('ContasBancarias', on_delete=models.PROTECT, blank=True, null=True, verbose_name="Conta Sacada")

    # Informações administrativas
    status = models.ForeignKey('StatusChoicesProcesso', on_delete=models.PROTECT, blank=True, null=True)
    detalhamento = models.CharField(max_length=200, blank=True, null=True)
    tag = models.ForeignKey('TagChoices', on_delete=models.PROTECT, blank=True, null=True)

    arquivo_final = models.FileField("Processo Consolidado", upload_to='processos_arquivados/', null=True, blank=True)
    em_contingencia = models.BooleanField(
        "Em Contingência",
        default=False,
        help_text="Indica que existe uma Contingência ativa para este processo. Nenhuma operação financeira pode ser realizada enquanto este flag estiver ativo."
    )
    history = HistoricalRecords()

    class Meta:
        permissions = [
            ("acesso_backoffice", "Pode acessar as telas gerais do sistema financeiro"),
            ("pode_operar_contas_pagar", "Pode empenhar, triar notas e fazer conferência"),
            ("pode_atestar_liquidacao", "Pode atestar notas fiscais (Fiscal do Contrato)"),
            ("pode_autorizar_pagamento", "Pode autorizar pagamentos (Ordenador)"),
            ("pode_contabilizar", "Pode registrar a contabilização (Contador)"),
            ("pode_auditar_conselho", "Pode aprovar no Conselho Fiscal"),
        ]

    def __str__(self):
        return f"Processo {self.n_nota_empenho or 'S/N'}"


# 2. DOCUMENTO DO PROCESSO
class DocumentoProcesso(DocumentoBase):
    processo = models.ForeignKey('Processo', on_delete=models.CASCADE, related_name='documentos')
    codigo_barras = models.CharField("Código de Barras", max_length=60, null=True, blank=True)
    imutavel = models.BooleanField(
        "Imutável",
        default=False,
        help_text="Documento bloqueado para exclusão. Definido automaticamente durante a etapa de Conferência."
    )
    history = HistoricalRecords()


class Pendencia(models.Model):
    processo = models.ForeignKey('Processo', on_delete=models.CASCADE, related_name='pendencias')
    status = models.ForeignKey('StatusChoicesPendencias', on_delete=models.PROTECT, blank=True, null=True)
    tipo = models.ForeignKey('TiposDePendencias', on_delete=models.PROTECT)
    descricao = models.CharField(max_length=200, blank=True, null=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"PENDÊNCIA: {self.tipo} - {self.descricao}"


class Contingencia(models.Model):
    # Metadados principais
    processo = models.ForeignKey(
        'Processo',
        on_delete=models.CASCADE,
        related_name='contingencias'
    )
    solicitante = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='contingencias_solicitadas'
    )
    data_solicitacao = models.DateTimeField(auto_now_add=True)
    justificativa = models.TextField(
        help_text="Motivo detalhado para a quebra de fluxo/retificação."
    )

    # O Payload (JSON com as mudanças propostas)
    dados_propostos = models.JSONField(
        default=dict,
        help_text="Dicionário JSON contendo o estado exato dos campos que serão alterados no Processo (ex: {'credor_id': 5})."
    )

    # Status FSM
    status = models.CharField(
        max_length=30,
        choices=STATUS_CONTINGENCIA,
        default='PENDENTE_SUPERVISOR'
    )

    # Etapa 1: Assinatura do Supervisor
    parecer_supervisor = models.TextField(blank=True, null=True)
    aprovado_por_supervisor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='cont_supervisionadas',
        null=True,
        blank=True
    )
    data_aprovacao_supervisor = models.DateTimeField(null=True, blank=True)

    # Etapa 2: Assinatura do Ordenador de Despesa
    parecer_ordenador = models.TextField(blank=True, null=True)
    aprovado_por_ordenador = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='cont_ordenadas',
        null=True,
        blank=True
    )
    data_aprovacao_ordenador = models.DateTimeField(null=True, blank=True)

    # Etapa 3: Assinatura do Conselho Fiscal (Condicional)
    parecer_conselho = models.TextField(blank=True, null=True)
    aprovado_por_conselho = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='cont_conselho',
        null=True,
        blank=True
    )
    data_aprovacao_conselho = models.DateTimeField(null=True, blank=True)

    # Trilha de auditoria
    history = HistoricalRecords()

    def __str__(self):
        return f"Contingência #{self.pk} - Processo {self.processo} [{self.get_status_display()}]"

    class Meta:
        verbose_name = "Contingência"
        verbose_name_plural = "Contingências"
        ordering = ['-data_solicitacao']
