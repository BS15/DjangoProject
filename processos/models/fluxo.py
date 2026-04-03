"""Modelos centrais do fluxo financeiro, auditoria e gestão documental."""

import os
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db.models.signals import post_delete, pre_save, pre_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords
from datetime import date
from processos.validators import validar_arquivo_seguro
from processos.utils import mesclar_pdfs_em_memoria


# Substitua a sua função antiga por esta:
def caminho_documento(instance, filename):
    """Resolve o diretório de upload conforme entidade de negócio vinculada."""
    # 1. Processo Principal
    if hasattr(instance, 'processo') and instance.processo:
        ano = instance.processo.data_empenho.year if instance.processo.data_empenho else (instance.processo.ano_exercicio or 9999)
        return f'pagamentos/{ano}/proc_{instance.processo.id}/{filename}'

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
    """Catálogo de status possíveis do processo de pagamento."""

    # This replaces your hard-coded choices
    status_choice = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.status_choice}"


class StatusChoicesPendencias(models.Model):
    """Catálogo de status aplicáveis às pendências."""

    # This replaces your hard-coded choices
    status_choice = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.status_choice}"


class TagChoices(models.Model):
    """Etiquetas administrativas usadas para classificação de processos."""

    # This replaces your hard-coded choices
    tag_choice = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tag_choice}"


class FormasDePagamento(models.Model):
    """Formas de pagamento aceitas no fluxo financeiro."""

    # This replaces your hard-coded choices
    forma_de_pagamento = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.forma_de_pagamento}"


class TiposDePagamento(models.Model):
    """Tipos de pagamento utilizados para agrupar regras de negócio."""

    # This replaces your hard-coded choices
    tipo_de_pagamento = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tipo_de_pagamento}"


class TiposDeDocumento(models.Model):
    """Tipos documentais por contexto de pagamento."""

    # This replaces your hard-coded choices
    tipo_de_pagamento = models.ForeignKey('TiposDePagamento', on_delete=models.PROTECT, blank=True, null=True)
    tipo_de_documento = models.CharField(max_length=100)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['tipo_de_documento', 'tipo_de_pagamento'],
                name='unique_documento_por_pagamento'
            )
        ]

    def __str__(self):
        if self.tipo_de_pagamento:
            return f"{self.tipo_de_documento} ({self.tipo_de_pagamento})"
        return f"{self.tipo_de_documento} (Geral)"


class TiposDePendencias(models.Model):
    """Tipos de pendências operacionais/documentais do processo."""

    # This replaces your hard-coded choices
    tipo_de_pendencia = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tipo_de_pendencia}"


class DocumentoBase(models.Model):
    """Classe abstrata base para documentos anexados com ordenação."""

    arquivo = models.FileField(upload_to=caminho_documento, validators=[validar_arquivo_seguro])
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


class ReuniaoConselho(models.Model):
    """Reunião do conselho fiscal usada para análise em lote de processos."""

    numero = models.IntegerField("Número da Reunião", help_text="Ex: 16 para a 16ª Reunião")
    data_reuniao = models.DateField("Data da Reunião", null=True, blank=True)
    trimestre_referencia = models.CharField(
        "Trimestre/Ano de Referência",
        max_length=50,
        help_text="Ex: 1º Trimestre / 2026",
    )
    status = models.CharField(
        "Status",
        max_length=20,
        choices=[
            ('AGENDADA', 'Agendada/Em Montagem'),
            ('EM_ANALISE', 'Em Análise pelo Conselho'),
            ('CONCLUIDA', 'Concluída'),
        ],
        default='AGENDADA',
    )

    class Meta:
        verbose_name = "Reunião do Conselho"
        verbose_name_plural = "Reuniões do Conselho"
        ordering = ['-numero']

    def __str__(self):
        return f"{self.numero}ª Reunião - {self.trimestre_referencia}"


class Processo(models.Model):
    """Entidade principal do ciclo orçamentário e financeiro do pagamento."""

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
    conta = models.ForeignKey('ContasBancarias', on_delete=models.SET_NULL, null=True, blank=True, related_name='processos_sacados', verbose_name="Conta Sacada")

    # Informações administrativas
    status = models.ForeignKey('StatusChoicesProcesso', on_delete=models.PROTECT, blank=True, null=True)
    detalhamento = models.CharField(max_length=200, blank=True, null=True)
    tag = models.ForeignKey('TagChoices', on_delete=models.PROTECT, blank=True, null=True)

    arquivo_final = models.FileField("Processo Consolidado", upload_to='processos_arquivados/', null=True, blank=True, validators=[validar_arquivo_seguro])
    em_contingencia = models.BooleanField(
        "Em Contingência",
        default=False,
        help_text="Indica que existe uma Contingência ativa para este processo. Nenhuma operação financeira pode ser realizada enquanto este flag estiver ativo."
    )
    reuniao_conselho = models.ForeignKey(
        'ReuniaoConselho',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processos_em_pauta',
        verbose_name="Reunião do Conselho",
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
            ("pode_arquivar", "Pode realizar o arquivamento definitivo de processos"),
        ]

    def __str__(self):
        return f"Processo {self.n_nota_empenho or 'S/N'}"

    @property
    def valor_efetivo(self):
        """Retorna valor líquido descontado das devoluções registradas."""
        total_devolvido = self.devolucoes.aggregate(total=Sum('valor_devolvido'))['total'] or 0
        return self.valor_liquido - total_devolvido

    @property
    def detalhes_pagamento(self):
        """Produz resumo do meio de pagamento para exibição em interface."""
        forma = self.forma_pagamento.forma_de_pagamento.lower() if self.forma_pagamento else ''
        detalhe_tipo = "Não Especificado"
        detalhe_valor = "Verifique o processo"
        codigos_barras = None

        if 'boleto' in forma or 'gerenciador' in forma:
            detalhe_tipo = "Código de Barras"
            codigos_barras = [doc.codigo_barras for doc in self.documentos.all() if doc.codigo_barras]
            detalhe_valor = codigos_barras[0] if codigos_barras else "Não preenchido"
        elif 'pix' in forma:
            detalhe_tipo = "Chave PIX"
            detalhe_valor = self.credor.chave_pix if (self.credor and self.credor.chave_pix) else "Credor sem PIX cadastrado"
        elif 'transfer' in forma or 'ted' in forma:
            detalhe_tipo = "Conta Bancária"
            if self.conta:
                detalhe_valor = f"Banco: {self.conta.banco} | Ag: {self.conta.agencia} | CC: {self.conta.conta}"
            else:
                detalhe_valor = "Nenhuma conta vinculada"

        return {
            'tipo_formatado': detalhe_tipo,
            'valor_formatado': detalhe_valor,
            'codigos_barras': codigos_barras,
        }

    def gerar_pdf_consolidado(self):
        """Mescla documentos do processo por ordem e retorna PDF em memória."""
        lista_caminhos = []
        for doc in self.documentos.order_by('ordem'):
            if doc.arquivo and doc.arquivo.name:
                if os.path.exists(doc.arquivo.path):
                    lista_caminhos.append(doc.arquivo.path)

        if not lista_caminhos:
            return None
        return mesclar_pdfs_em_memoria(lista_caminhos)

    def avancar_status(self, novo_status_str, usuario=None):
        """Avança status validando turnpike e propaga pagamento para diárias vinculadas."""
        from django.core.exceptions import ValidationError
        from processos.validators import verificar_turnpike
        status_anterior = self.status.status_choice if self.status else ''
        erros = verificar_turnpike(self, status_anterior, novo_status_str)
        if erros:
            raise ValidationError(erros)
        novo_status, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact=novo_status_str,
            defaults={'status_choice': novo_status_str}
        )
        self.status = novo_status

        if usuario:
            self._history_user = usuario

        self.save(update_fields=['status'])

        if novo_status_str.upper().startswith('PAGO'):
            from processos.models.verbas import StatusChoicesVerbasIndenizatorias
            status_paga, _ = StatusChoicesVerbasIndenizatorias.objects.get_or_create(
                status_choice='PAGA'
            )
            for diaria in self.diarias.all():
                diaria.status = status_paga
                if usuario:
                    diaria._history_user = usuario
                diaria.save(update_fields=['status'])


# 2. DOCUMENTO DO PROCESSO
class DocumentoProcesso(DocumentoBase):
    """Documento anexado ao processo com controle de imutabilidade."""

    processo = models.ForeignKey('Processo', on_delete=models.CASCADE, related_name='documentos')
    codigo_barras = models.CharField("Código de Barras", max_length=60, null=True, blank=True)
    imutavel = models.BooleanField(
        "Imutável",
        default=False,
        help_text="Documento bloqueado para exclusão. Definido automaticamente durante a etapa de Conferência."
    )
    history = HistoricalRecords()


class Pendencia(models.Model):
    """Pendência operacional ou documental atrelada ao processo."""

    processo = models.ForeignKey('Processo', on_delete=models.CASCADE, related_name='pendencias')
    status = models.ForeignKey('StatusChoicesPendencias', on_delete=models.PROTECT, blank=True, null=True)
    tipo = models.ForeignKey('TiposDePendencias', on_delete=models.PROTECT)
    descricao = models.CharField(max_length=200, blank=True, null=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"PENDÊNCIA: {self.tipo} - {self.descricao}"


class Contingencia(models.Model):
    """Solicitação formal de retificação com trilha de aprovação multi-etapa."""

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


class RegistroAcessoArquivo(models.Model):
    """Log de acesso a arquivos para auditoria e rastreabilidade."""

    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    nome_arquivo = models.CharField(max_length=500)
    data_acesso = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.usuario} acessou {self.nome_arquivo}"

    class Meta:
        verbose_name = "Registro de Acesso a Arquivo"
        verbose_name_plural = "Registros de Acesso a Arquivos"
        ordering = ['-data_acesso']


class Devolucao(models.Model):
    """Registro de devolução de valores relacionados ao processo."""

    processo = models.ForeignKey('Processo', on_delete=models.CASCADE, related_name='devolucoes')
    valor_devolvido = models.DecimalField(max_digits=15, decimal_places=2)
    data_devolucao = models.DateField()
    motivo = models.TextField()
    comprovante = models.FileField(upload_to='devolucoes/', validators=[validar_arquivo_seguro], help_text="Comprovante de depósito/GRU")
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Devolução de R$ {self.valor_devolvido} - Processo {self.processo}"

    class Meta:
        verbose_name = "Devolução"
        verbose_name_plural = "Devoluções"
        ordering = ['-data_devolucao']


class AssinaturaAutentique(models.Model):
    """Metadados de integração com assinatura eletrônica via Autentique."""

    STATUS_CHOICES = [
        ('RASCUNHO', 'Rascunho'),
        ('PENDENTE', 'Pendente'),
        ('ASSINADO', 'Assinado'),
        ('REJEITADO', 'Rejeitado'),
        ('ERRO', 'Erro'),
    ]

    # Generic Relation to link to Diaria, Processo, Reembolso, etc.
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    entidade_relacionada = GenericForeignKey('content_type', 'object_id')

    criador = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assinaturas_criadas')
    tipo_documento = models.CharField("Tipo do Documento", max_length=50, help_text="Ex: SCD, PCD, AUTORIZACAO")
    autentique_id = models.CharField("ID Autentique", max_length=100, unique=True, null=True, blank=True)
    autentique_url = models.URLField("URL para Assinatura", max_length=500, blank=True, default='')
    dados_signatarios = models.JSONField("Dados dos Signatários", default=dict, blank=True, null=True)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default='RASCUNHO')
    arquivo = models.FileField("Arquivo (Rascunho)", upload_to='assinaturas_rascunho/', null=True, blank=True)
    arquivo_assinado = models.FileField("Arquivo Assinado", upload_to='documentos_assinados/', null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.tipo_documento} - {self.autentique_id} ({self.status})"


# ==============================================================================
# FILE LIFECYCLE SIGNALS
# ==============================================================================

def _delete_file(file_field):
    """Remove arquivo do storage, ignorando erros quando inexistente."""
    if file_field and file_field.name:
        try:
            file_field.storage.delete(file_field.name)
        except Exception:
            pass


@receiver(post_delete, sender=DocumentoProcesso)
def auto_delete_file_on_delete_documentoprocesso(sender, instance, **kwargs):
    """Remove arquivo físico quando DocumentoProcesso é excluído."""
    _delete_file(instance.arquivo)


@receiver(pre_save, sender=DocumentoProcesso)
def enforce_immutability_and_cleanup_on_save(sender, instance, **kwargs):
    """Bloqueia troca de arquivo em documento imutável e limpa versão anterior."""
    if not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    if old.imutavel:
        if instance.arquivo.name != old.arquivo.name:
            raise ValidationError(
                "Este documento é imutável e não pode ter seu arquivo substituído."
            )
    if old.arquivo and old.arquivo.name and old.arquivo.name != instance.arquivo.name:
        _delete_file(old.arquivo)


@receiver(pre_delete, sender=DocumentoProcesso)
def prevent_immutable_delete(sender, instance, **kwargs):
    """Impede exclusão de documentos marcados como imutáveis."""
    if instance.imutavel:
        raise ValidationError(
            "Este documento é imutável e não pode ser excluído."
        )
