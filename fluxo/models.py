"""Modelos centrais do fluxo financeiro, auditoria e gestão documental."""

import logging
from django.db import models
from django.db.models import Max, Sum
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db.models.signals import post_delete, pre_save, pre_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from simple_history.models import HistoricalRecords
from datetime import date, datetime
from fluxo.validators import validar_arquivo_seguro
from fluxo.utils import mesclar_pdfs_em_memoria
from commons.shared.storage_utils import caminho_documento, _delete_file

logger = logging.getLogger(__name__)


class StatusChoicesProcesso(models.Model):
    """Catálogo de status possíveis do processo de pagamento."""

    status_choice = models.CharField(max_length=100, unique=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.status_choice}"


class StatusChoicesPendencias(models.Model):
    """Catálogo de status aplicáveis às pendências."""

    status_choice = models.CharField(max_length=100, unique=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.status_choice}"


class TagChoices(models.Model):
    """Etiquetas administrativas usadas para classificação de processos."""

    tag_choice = models.CharField(max_length=100, unique=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tag_choice}"


class FormasDePagamento(models.Model):
    """Formas de pagamento aceitas no fluxo financeiro."""

    forma_de_pagamento = models.CharField(max_length=100, unique=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.forma_de_pagamento}"


class TiposDePagamento(models.Model):
    """Tipos de pagamento utilizados para agrupar regras de negócio."""

    tipo_de_pagamento = models.CharField(max_length=100, unique=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tipo_de_pagamento}"


class TiposDeDocumento(models.Model):
    """Tipos documentais por contexto de pagamento."""

    tipo_de_pagamento = models.ForeignKey('TiposDePagamento', on_delete=models.PROTECT, blank=True, null=True)
    tipo_de_documento = models.CharField(max_length=100)

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

    tipo_de_pendencia = models.CharField(max_length=100, unique=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tipo_de_pendencia}"


class DocumentoBase(models.Model):
    """Classe abstrata base para documentos anexados com ordenação."""

    arquivo = models.FileField(upload_to=caminho_documento, validators=[validar_arquivo_seguro])
    ordem = models.PositiveIntegerField(default=1, help_text="Ordem do arquivo")
    tipo = models.ForeignKey('fluxo.TiposDeDocumento', on_delete=models.PROTECT)

    class Meta:
        abstract = True
        ordering = ['ordem']


STATUS_CONTINGENCIA = [
    ('PENDENTE_SUPERVISOR', 'Pendente Supervisor'),
    ('PENDENTE_ORDENADOR', 'Pendente Ordenador de Despesa'),
    ('PENDENTE_CONSELHO', 'Pendente Conselho Fiscal'),
    ('PENDENTE_CONTADOR', 'Pendente Revisão da Contadora'),
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


class ProcessoManager(models.Manager):
    """Manager com compatibilidade para kwargs legados de empenho."""

    def create(self, **kwargs):
        numero_nota_empenho = kwargs.pop("n_nota_empenho", None)
        data_empenho = kwargs.pop("data_empenho", None)
        ano_exercicio = kwargs.pop("ano_exercicio", None)

        processo = super().create(**kwargs)
        if any(v not in (None, "") for v in (numero_nota_empenho, data_empenho, ano_exercicio)):
            processo.registrar_documento_orcamentario(
                numero_nota_empenho=numero_nota_empenho,
                data_empenho=data_empenho,
                ano_exercicio=ano_exercicio,
            )
        return processo


class Processo(models.Model):
    """Entidade principal do ciclo orçamentário e financeiro do pagamento."""

    extraorcamentario = models.BooleanField(
        "Extraorçamentário",
        default=False,
        help_text="Marque se este processo não utiliza dotação orçamentária (ex: cauções)."
    )
    credor = models.ForeignKey('credores.Credor', on_delete=models.PROTECT, blank=False, null=False)
    valor_bruto = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    valor_liquido = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])

    n_pagamento_siscac = models.CharField(max_length=50, blank=True, null=True)
    data_vencimento = models.DateField(blank=True, null=True)
    data_pagamento = models.DateField(blank=True, null=True)
    forma_pagamento = models.ForeignKey('FormasDePagamento', on_delete=models.PROTECT, blank=False, null=False)
    tipo_pagamento = models.ForeignKey('TiposDePagamento', on_delete=models.PROTECT, blank=False, null=False)
    observacao = models.CharField(max_length=200, blank=True, null=True)
    conta = models.ForeignKey('credores.ContasBancarias', on_delete=models.SET_NULL, null=True, blank=True, related_name='processos_sacados', verbose_name="Conta Sacada")

    status = models.ForeignKey('StatusChoicesProcesso', on_delete=models.PROTECT, blank=False, null=False)
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
    objects = ProcessoManager()

    class Meta:
        permissions = [
            ("acesso_backoffice", "Pode acessar as telas gerais do sistema financeiro"),
            ("pode_operar_contas_pagar", "Pode empenhar, triar notas e fazer conferência"),
            ("pode_aprovar_contingencia_supervisor", "Pode aprovar contingências na etapa de supervisão/gerência"),
            ("pode_atestar_liquidacao", "Pode atestar notas fiscais (Fiscal do Contrato)"),
            ("pode_autorizar_pagamento", "Pode autorizar pagamentos (Ordenador)"),
            ("pode_contabilizar", "Pode registrar a contabilização (Contador)"),
            ("pode_auditar_conselho", "Pode aprovar no Conselho Fiscal"),
            ("pode_arquivar", "Pode realizar o arquivamento definitivo de processos"),
            ("pode_visualizar_verbas", "Pode visualizar painéis e listas de verbas indenizatórias"),
            ("pode_criar_diarias", "Pode cadastrar solicitações de diárias"),
            ("pode_importar_diarias", "Pode importar diárias em lote"),
            ("pode_gerenciar_diarias", "Pode editar diárias e seus documentos"),
            ("pode_autorizar_diarias", "Pode autorizar e aprovar diárias"),
            ("pode_gerenciar_reembolsos", "Pode cadastrar e editar reembolsos de combustível"),
            ("pode_gerenciar_jetons", "Pode cadastrar e editar jetons"),
            ("pode_gerenciar_auxilios", "Pode cadastrar e editar auxílios representação"),
            ("pode_agrupar_verbas", "Pode agrupar verbas em processos de pagamento"),
            ("pode_gerenciar_processos_verbas", "Pode editar processos originados de verbas indenizatórias"),
            ("pode_sincronizar_diarias_siscac", "Pode sincronizar/importar diárias via SISCAC"),
        ]

    def __str__(self):
        return f"Processo {self.n_nota_empenho or 'S/N'}"

    def _set_pending_documento_orcamentario_field(self, field_name, value):
        pending = getattr(self, "_pending_documento_orcamentario", {})
        pending[field_name] = value
        self._pending_documento_orcamentario = pending

    def _persist_pending_documento_orcamentario(self):
        pending = getattr(self, "_pending_documento_orcamentario", None)
        if not pending or not self.pk:
            return

        atual = self.documentos_orcamentarios.order_by("-data_empenho", "-id").first()

        numero_nota_empenho = pending.get(
            "numero_nota_empenho",
            atual.numero_nota_empenho if atual else None,
        )
        data_empenho = pending.get("data_empenho", atual.data_empenho if atual else None)
        ano_exercicio = pending.get("ano_exercicio", atual.ano_exercicio if atual else None)

        if data_empenho and not ano_exercicio:
            ano_exercicio = data_empenho.year

        if any(v not in (None, "") for v in (numero_nota_empenho, data_empenho, ano_exercicio)):
            DocumentoOrcamentario.objects.create(
                processo=self,
                numero_nota_empenho=numero_nota_empenho,
                data_empenho=data_empenho,
                ano_exercicio=ano_exercicio,
            )

        self._pending_documento_orcamentario = {}

    @property
    def documento_orcamentario_principal(self):
        return self.documentos_orcamentarios.order_by("-data_empenho", "-id").first()

    @property
    def n_nota_empenho(self):
        doc = self.documento_orcamentario_principal
        return doc.numero_nota_empenho if doc else None

    @n_nota_empenho.setter
    def n_nota_empenho(self, value):
        self._set_pending_documento_orcamentario_field("numero_nota_empenho", value)

    @property
    def data_empenho(self):
        doc = self.documento_orcamentario_principal
        return doc.data_empenho if doc else None

    @data_empenho.setter
    def data_empenho(self, value):
        self._set_pending_documento_orcamentario_field("data_empenho", value)

    @property
    def ano_exercicio(self):
        doc = self.documento_orcamentario_principal
        return doc.ano_exercicio if doc else None

    @ano_exercicio.setter
    def ano_exercicio(self, value):
        self._set_pending_documento_orcamentario_field("ano_exercicio", value)

    def registrar_documento_orcamentario(self, numero_nota_empenho=None, data_empenho=None, ano_exercicio=None):
        """Registra um novo documento orçamentário mantendo histórico de versões."""
        if isinstance(data_empenho, str):
            data_empenho = datetime.strptime(data_empenho, "%Y-%m-%d").date()

        if data_empenho and not ano_exercicio:
            ano_exercicio = data_empenho.year

        if not any(v not in (None, "") for v in (numero_nota_empenho, data_empenho, ano_exercicio)):
            return None

        return DocumentoOrcamentario.objects.create(
            processo=self,
            numero_nota_empenho=numero_nota_empenho,
            data_empenho=data_empenho,
            ano_exercicio=ano_exercicio,
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._persist_pending_documento_orcamentario()

    def clean(self):
        """Valida integridade dos dados do processo antes de salvar."""
        errors = {}

        if self.valor_liquido and self.valor_bruto:
            if self.valor_liquido > self.valor_bruto:
                errors['valor_liquido'] = 'Valor líquido não pode ser maior que o valor bruto.'

        if self.data_pagamento and self.data_vencimento:
            if self.data_pagamento < self.data_vencimento:
                errors['data_pagamento'] = 'Data de pagamento não pode ser anterior à data de vencimento.'

        if not self.credor_id:
            errors['credor'] = 'Credor é obrigatório.'

        if not self.forma_pagamento_id:
            errors['forma_pagamento'] = 'Forma de pagamento é obrigatória.'

        if not self.tipo_pagamento_id:
            errors['tipo_pagamento'] = 'Tipo de pagamento é obrigatório.'

        if not self.status_id:
            errors['status'] = 'Status é obrigatório.'

        if errors:
            raise ValidationError(errors)

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
        from fluxo.utils import PdfMergeError

        lista_caminhos = []
        for doc in self.documentos.order_by('ordem'):
            if doc.arquivo and doc.arquivo.name:
                if os.path.exists(doc.arquivo.path):
                    lista_caminhos.append(doc.arquivo.path)

        if not lista_caminhos:
            return None

        try:
            return mesclar_pdfs_em_memoria(lista_caminhos)
        except PdfMergeError as exc:
            logger.exception("Falha ao gerar PDF consolidado do processo %s", self.id)
            raise RuntimeError(f"Falha técnica ao consolidar PDFs do processo {self.id}.") from exc

    def _obter_tipo_documento_gerado(self, nome_tipo_documento):
        """Resolve (ou cria) o tipo de documento para anexos gerados automaticamente."""
        if self.tipo_pagamento_id:
            doc_tipo = TiposDeDocumento.objects.filter(
                tipo_de_documento__iexact=nome_tipo_documento,
                tipo_de_pagamento=self.tipo_pagamento,
            ).first()
            if doc_tipo:
                return doc_tipo

        doc_tipo_geral = TiposDeDocumento.objects.filter(
            tipo_de_documento__iexact=nome_tipo_documento,
            tipo_de_pagamento__isnull=True,
        ).first()
        if doc_tipo_geral:
            return doc_tipo_geral

        return TiposDeDocumento.objects.create(
            tipo_de_documento=nome_tipo_documento,
            tipo_de_pagamento=self.tipo_pagamento if self.tipo_pagamento_id else None,
        )

    def _anexar_pdf_gerado(self, pdf_bytes, nome_arquivo, tipo_documento_nome):
        """Anexa PDF gerado como DocumentoDePagamento na próxima ordem disponível."""
        from django.core.files.base import ContentFile

        if self.documentos.filter(arquivo__icontains=nome_arquivo).exists():
            raise ValidationError(
                f"Documento automático já existe para o processo {self.id}: {nome_arquivo}"
            )

        proxima_ordem = (self.documentos.aggregate(max_ordem=Max("ordem"))["max_ordem"] or 0) + 1
        tipo_documento = self._obter_tipo_documento_gerado(tipo_documento_nome)

        DocumentoDePagamento.objects.create(
            processo=self,
            arquivo=ContentFile(pdf_bytes, name=nome_arquivo),
            tipo=tipo_documento,
            ordem=proxima_ordem,
        )
        return True

    def _gerar_anexo_por_tipo(self, doc_type, obj, nome_arquivo, tipo_documento_nome, **kwargs):
        """Gera PDF via engine e anexa ao processo sem duplicar arquivo."""
        from fluxo.services.fluxo import (
            DocumentoGeradoDuplicadoError,
            gerar_e_anexar_documento_processo,
        )

        try:
            return gerar_e_anexar_documento_processo(
                self,
                doc_type,
                obj,
                nome_arquivo,
                tipo_documento_nome,
                **kwargs,
            )
        except DocumentoGeradoDuplicadoError:
            logger.info(
                "Documento automático duplicado ignorado no processo %s: %s",
                self.id,
                nome_arquivo,
            )
            return None

    def _gerar_documentos_automaticos(self, status_anterior, novo_status):
        """Gera e anexa documentos automáticos conforme transição de status."""
        try:
            if novo_status == "A PAGAR - AUTORIZADO":
                self._gerar_anexo_por_tipo(
                    "autorizacao",
                    self,
                    f"Termo_Autorizacao_Proc_{self.id}.pdf",
                    "TERMO DE AUTORIZAÇÃO DE PAGAMENTO",
                )

            if novo_status == "CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL":
                self._gerar_anexo_por_tipo(
                    "contabilizacao",
                    self,
                    f"Termo_Contabilizacao_Proc_{self.id}.pdf",
                    "TERMO DE CONTABILIZAÇÃO",
                )
                self._gerar_anexo_por_tipo(
                    "auditoria",
                    self,
                    f"Termo_Auditoria_Proc_{self.id}.pdf",
                    "TERMO DE AUDITORIA",
                )

            if novo_status == "APROVADO - PENDENTE ARQUIVAMENTO":
                numero_reuniao = self.reuniao_conselho.numero if self.reuniao_conselho else None
                self._gerar_anexo_por_tipo(
                    "conselho_fiscal",
                    self,
                    f"Parecer_Conselho_Fiscal_Proc_{self.id}.pdf",
                    "PARECER DO CONSELHO FISCAL",
                    numero_reuniao=numero_reuniao,
                )

            entrou_em_pago = not status_anterior.startswith("PAGO") and novo_status.startswith("PAGO")
            if entrou_em_pago:
                for diaria in self.diarias.all():
                    identificador = diaria.numero_siscac or diaria.id
                    self._gerar_anexo_por_tipo(
                        "pcd",
                        diaria,
                        f"PCD_{identificador}.pdf",
                        "PROPOSTA DE CONCESSÃO DE DIÁRIAS (PCD)",
                    )

                for reembolso in self.reembolsos_combustivel.all():
                    identificador = reembolso.numero_sequencial or reembolso.id
                    self._gerar_anexo_por_tipo(
                        "recibo_reembolso",
                        reembolso,
                        f"Recibo_Reembolso_{identificador}.pdf",
                        "RECIBO DE PAGAMENTO",
                    )

                for jeton in self.jetons.all():
                    identificador = jeton.numero_sequencial or jeton.id
                    self._gerar_anexo_por_tipo(
                        "recibo_jeton",
                        jeton,
                        f"Recibo_Jeton_{identificador}.pdf",
                        "RECIBO DE PAGAMENTO",
                    )

                for auxilio in self.auxilios_representacao.all():
                    identificador = auxilio.numero_sequencial or auxilio.id
                    self._gerar_anexo_por_tipo(
                        "recibo_auxilio",
                        auxilio,
                        f"Recibo_Auxilio_{identificador}.pdf",
                        "RECIBO DE PAGAMENTO",
                    )

                for suprimento in self.suprimentos.all():
                    self._gerar_anexo_por_tipo(
                        "recibo_suprimento",
                        suprimento,
                        f"Recibo_Suprimento_{suprimento.id}.pdf",
                        "RECIBO DE PAGAMENTO",
                    )
        except (ValidationError, OSError, RuntimeError, TypeError, ValueError):
            logger.exception(
                "Falha ao gerar anexos automáticos do processo %s na transição '%s' -> '%s'",
                self.id,
                status_anterior,
                novo_status,
            )

    def disparar_documentos_automaticos_por_status(self, status_anterior, novo_status):
        """Dispara geração automática de documentos para transições feitas fora de ``avancar_status``."""
        self._gerar_documentos_automaticos((status_anterior or "").upper(), (novo_status or "").upper())

    def avancar_status(self, novo_status_str, usuario=None):
        """Avança status validando turnpike e propaga pagamento para diárias vinculadas."""
        from django.core.exceptions import ValidationError
        from fluxo.validators import verificar_turnpike
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

        status_anterior_norm = (status_anterior or "").upper()
        novo_status_norm = (novo_status_str or "").upper()
        self._gerar_documentos_automaticos(status_anterior_norm, novo_status_norm)

        if novo_status_norm.startswith('PAGO'):
            from verbas_indenizatorias.models import StatusChoicesVerbasIndenizatorias
            status_paga, _ = StatusChoicesVerbasIndenizatorias.objects.get_or_create(
                status_choice='PAGA'
            )
            for diaria in self.diarias.all():
                diaria.status = status_paga
                if usuario:
                    diaria._history_user = usuario
                diaria.save(update_fields=['status'])


class DocumentoDePagamento(DocumentoBase):
    """Documento anexado ao processo com controle de imutabilidade."""

    processo = models.ForeignKey('Processo', on_delete=models.CASCADE, related_name='documentos')
    codigo_barras = models.CharField("Código de Barras", max_length=60, null=True, blank=True)
    imutavel = models.BooleanField(
        "Imutável",
        default=False,
        help_text="Documento bloqueado para exclusão. Definido automaticamente durante a etapa de Conferência."
    )
    history = HistoricalRecords()


# Alias de compatibilidade transitória.
DocumentoProcesso = DocumentoDePagamento


class DocumentoOrcamentario(DocumentoBase):
    """Documento orçamentário (nota/data/ano de empenho) vinculado ao processo."""

    processo = models.ForeignKey("Processo", on_delete=models.CASCADE, related_name="documentos_orcamentarios")
    arquivo = models.FileField(upload_to=caminho_documento, validators=[validar_arquivo_seguro], blank=True, null=True)
    tipo = models.ForeignKey('TiposDeDocumento', on_delete=models.PROTECT, blank=True, null=True)
    numero_nota_empenho = models.CharField(max_length=50, blank=True, null=True)
    data_empenho = models.DateField(blank=True, null=True)
    ano_exercicio = models.IntegerField(
        choices=[(y, y) for y in range(2020, 2035)],
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

    dados_propostos = models.JSONField(
        default=dict,
        help_text="Dicionário JSON contendo o estado exato dos campos que serão alterados no Processo (ex: {'credor_id': 5})."
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CONTINGENCIA,
        default='PENDENTE_SUPERVISOR'
    )
    exige_aprovacao_ordenador = models.BooleanField(default=False)
    exige_aprovacao_conselho = models.BooleanField(default=False)
    exige_revisao_contadora = models.BooleanField(default=True)

    parecer_supervisor = models.TextField(blank=True, null=True)
    aprovado_por_supervisor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='cont_supervisionadas',
        null=True,
        blank=True
    )
    data_aprovacao_supervisor = models.DateTimeField(null=True, blank=True)

    parecer_ordenador = models.TextField(blank=True, null=True)
    aprovado_por_ordenador = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='cont_ordenadas',
        null=True,
        blank=True
    )
    data_aprovacao_ordenador = models.DateTimeField(null=True, blank=True)

    parecer_conselho = models.TextField(blank=True, null=True)
    aprovado_por_conselho = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='cont_conselho',
        null=True,
        blank=True
    )
    data_aprovacao_conselho = models.DateTimeField(null=True, blank=True)

    parecer_contadora = models.TextField(blank=True, null=True)
    revisado_por_contadora = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='cont_revisadas_contadora',
        null=True,
        blank=True
    )
    data_revisao_contadora = models.DateTimeField(null=True, blank=True)

    history = HistoricalRecords()

    def __str__(self):
        return f"Contingência #{self.pk} - Processo {self.processo} [{self.get_status_display()}]"

    class Meta:
        verbose_name = "Contingência"
        verbose_name_plural = "Contingências"
        ordering = ['-data_solicitacao']


class RegistroAcessoArquivo(models.Model):
    """Log de acesso a arquivos para auditoria e rastreabilidade."""

    usuario = models.ForeignKey(User, on_delete=models.PROTECT, null=True)
    nome_arquivo = models.CharField(max_length=500)
    data_acesso = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.usuario} acessou {self.nome_arquivo}"

    class Meta:
        verbose_name = "Registro de Acesso a Arquivo"
        verbose_name_plural = "Registros de Acesso a Arquivos"
        ordering = ['-data_acesso']


class Devolucao(models.Model):
    """Registro de devolução de valores relacionados ao processo."""

    processo = models.ForeignKey('Processo', on_delete=models.CASCADE, related_name='devolucoes')
    valor_devolvido = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0.01)])
    data_devolucao = models.DateField()
    motivo = models.TextField()
    comprovante = models.FileField(upload_to='devolucoes/', validators=[validar_arquivo_seguro], help_text="Comprovante de depósito/GRU")
    criado_em = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    def clean(self):
        """Valida que devolução não excede valor líquido do processo."""
        if self.processo_id:
            total_devolvido = self.processo.devolucoes.exclude(pk=self.pk).aggregate(t=Sum('valor_devolvido'))['t'] or 0
            total_com_esta = total_devolvido + self.valor_devolvido
            if total_com_esta > self.processo.valor_liquido:
                raise ValidationError(
                    f'Total de devoluções ({total_com_esta}) não pode exceder valor líquido ({self.processo.valor_liquido}).'
                )

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

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    entidade_relacionada = GenericForeignKey('content_type', 'object_id')

    criador = models.ForeignKey(User, on_delete=models.PROTECT, related_name='assinaturas_criadas')
    tipo_documento = models.CharField("Tipo do Documento", max_length=50, help_text="Ex: SCD, PCD, AUTORIZACAO")
    autentique_id = models.CharField("ID Autentique", max_length=100, unique=True, null=True, blank=True)
    autentique_url = models.URLField("URL para Assinatura", max_length=500, blank=True, default='')
    dados_signatarios = models.JSONField("Dados dos Signatários", default=dict, blank=True, null=True)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default='RASCUNHO')
    arquivo = models.FileField("Arquivo (Rascunho)", upload_to='assinaturas_rascunho/', null=True, blank=True)
    arquivo_assinado = models.FileField("Arquivo Assinado", upload_to='documentos_assinados/', null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.tipo_documento} - {self.autentique_id} ({self.status})"


@receiver(post_delete, sender=DocumentoDePagamento)
def auto_delete_file_on_delete_documentoprocesso(sender, instance, **kwargs):
    """Remove arquivo físico quando DocumentoDePagamento é excluído."""
    _delete_file(instance.arquivo)


@receiver(pre_save, sender=DocumentoDePagamento)
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


@receiver(pre_delete, sender=DocumentoDePagamento)
def prevent_immutable_delete(sender, instance, **kwargs):
    """Impede exclusão de documentos marcados como imutáveis."""
    if instance.imutavel:
        raise ValidationError(
            "Este documento é imutável e não pode ser excluído."
        )
