"""Modelos de processos e reuniões do domínio de fluxo financeiro.

Este módulo define modelos para processos, reuniões de conselho e gerenciadores relacionados ao ciclo de vida dos processos financeiros.
"""

from datetime import datetime

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from simple_history.models import HistoricalRecords

from commons.shared.file_validators import validar_arquivo_seguro


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
            ("AGENDADA", "Agendada/Em Montagem"),
            ("EM_ANALISE", "Em Análise pelo Conselho"),
            ("CONCLUIDA", "Concluída"),
        ],
        default="AGENDADA",
    )

    class Meta:
        verbose_name = "Reunião do Conselho"
        verbose_name_plural = "Reuniões do Conselho"
        ordering = ["-numero"]

    def __str__(self):
        return f"{self.numero}ª Reunião - {self.trimestre_referencia}"


class ProcessoManager(models.Manager):
    """Manager com compatibilidade para kwargs legados de empenho."""

    def create(self, **kwargs):
        numero_nota_empenho = kwargs.pop("n_nota_empenho", None)
        data_empenho = kwargs.pop("data_empenho", None)
        ano_exercicio = kwargs.pop("ano_exercicio", None)

        processo = super().create(**kwargs)
        if any(value not in (None, "") for value in (numero_nota_empenho, data_empenho, ano_exercicio)):
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
        help_text="Marque se este processo não utiliza dotação orçamentária (ex: cauções).",
    )
    credor = models.ForeignKey("credores.Credor", on_delete=models.PROTECT, blank=False, null=False)
    valor_bruto = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    valor_liquido = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])

    n_pagamento_siscac = models.CharField(max_length=50, blank=True, null=True)
    data_vencimento = models.DateField(blank=True, null=True)
    data_pagamento = models.DateField(blank=True, null=True)
    forma_pagamento = models.ForeignKey("fluxo.FormasDePagamento", on_delete=models.PROTECT, blank=False, null=False)
    tipo_pagamento = models.ForeignKey("fluxo.TiposDePagamento", on_delete=models.PROTECT, blank=False, null=False)
    observacao = models.CharField(max_length=200, blank=True, null=True)
    conta = models.ForeignKey(
        "credores.ContasBancarias",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processos_sacados",
        verbose_name="Conta Sacada",
    )

    status = models.ForeignKey("fluxo.StatusChoicesProcesso", on_delete=models.PROTECT, blank=False, null=False)
    detalhamento = models.CharField(max_length=200, blank=True, null=True)
    tag = models.ForeignKey("fluxo.TagChoices", on_delete=models.PROTECT, blank=True, null=True)

    arquivo_final = models.FileField(
        "Processo Consolidado",
        upload_to="processos_arquivados/",
        null=True,
        blank=True,
        validators=[validar_arquivo_seguro],
    )
    em_contingencia = models.BooleanField(
        "Em Contingência",
        default=False,
        help_text="Indica que existe uma Contingência ativa para este processo. Nenhuma operação financeira pode ser realizada enquanto este flag estiver ativo.",
    )
    reuniao_conselho = models.ForeignKey(
        "fluxo.ReuniaoConselho",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processos_em_pauta",
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

        if any(value not in (None, "") for value in (numero_nota_empenho, data_empenho, ano_exercicio)):
            from fluxo.models import DocumentoOrcamentario

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
        from fluxo.models import DocumentoOrcamentario

        if isinstance(data_empenho, str):
            data_empenho = datetime.strptime(data_empenho, "%Y-%m-%d").date()

        if data_empenho and not ano_exercicio:
            ano_exercicio = data_empenho.year

        if not any(value not in (None, "") for value in (numero_nota_empenho, data_empenho, ano_exercicio)):
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

        if self.valor_liquido and self.valor_bruto and self.valor_liquido > self.valor_bruto:
            errors["valor_liquido"] = "Valor líquido não pode ser maior que o valor bruto."

        if self.data_pagamento and self.data_vencimento and self.data_pagamento < self.data_vencimento:
            errors["data_pagamento"] = "Data de pagamento não pode ser anterior à data de vencimento."

        if not self.credor_id:
            errors["credor"] = "Credor é obrigatório."

        if not self.forma_pagamento_id:
            errors["forma_pagamento"] = "Forma de pagamento é obrigatória."

        if not self.tipo_pagamento_id:
            errors["tipo_pagamento"] = "Tipo de pagamento é obrigatório."

        if not self.status_id:
            errors["status"] = "Status é obrigatório."

        if errors:
            raise ValidationError(errors)

    @property
    def valor_efetivo(self):
        """Retorna valor líquido descontado das devoluções registradas."""
        total_devolvido = self.devolucoes.aggregate(total=Sum("valor_devolvido"))["total"] or 0
        return self.valor_liquido - total_devolvido

    @property
    def detalhes_pagamento(self):
        """Produz resumo do meio de pagamento para exibição em interface."""
        forma = self.forma_pagamento.forma_de_pagamento.lower() if self.forma_pagamento else ""
        detalhe_tipo = "Não Especificado"
        detalhe_valor = "Verifique o processo"
        codigos_barras = None

        if "boleto" in forma or "gerenciador" in forma:
            detalhe_tipo = "Código de Barras"
            codigos_barras = [doc.codigo_barras for doc in self.documentos.all() if doc.codigo_barras]
            detalhe_valor = codigos_barras[0] if codigos_barras else "Não preenchido"
        elif "pix" in forma:
            detalhe_tipo = "Chave PIX"
            detalhe_valor = self.credor.chave_pix if (self.credor and self.credor.chave_pix) else "Credor sem PIX cadastrado"
        elif "transfer" in forma or "ted" in forma:
            detalhe_tipo = "Conta Bancária"
            if self.conta:
                detalhe_valor = f"Banco: {self.conta.banco} | Ag: {self.conta.agencia} | CC: {self.conta.conta}"
            else:
                detalhe_valor = "Nenhuma conta vinculada"

        return {
            "tipo_formatado": detalhe_tipo,
            "valor_formatado": detalhe_valor,
            "codigos_barras": codigos_barras,
        }

    def gerar_pdf_consolidado(self):
        """Mescla documentos do processo por ordem e retorna PDF em memória."""
        from fluxo.services.processo_documentos import gerar_pdf_consolidado_processo

        return gerar_pdf_consolidado_processo(self)

    def disparar_documentos_automaticos_por_status(self, status_anterior, novo_status):
        """Dispara geração automática de documentos para transições feitas fora de avancar_status."""
        from fluxo.services.processo_documentos import gerar_documentos_automaticos_processo

        gerar_documentos_automaticos_processo(self, (status_anterior or "").upper(), (novo_status or "").upper())

    def avancar_status(self, novo_status_str, usuario=None):
        """Avança status validando turnpike e delega integrações aos serviços."""
        from fluxo.models import StatusChoicesProcesso
        from fluxo.services.integracoes.processo_relacionados import sincronizar_relacoes_apos_transicao
        from fluxo.services.processo_documentos import gerar_documentos_automaticos_processo
        from fluxo.validators import verificar_turnpike

        status_anterior = self.status.status_choice if self.status else ""
        erros = verificar_turnpike(self, status_anterior, novo_status_str)
        if erros:
            raise ValidationError(erros)

        novo_status, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact=novo_status_str,
            defaults={"status_choice": novo_status_str},
        )
        self.status = novo_status

        if usuario:
            self._history_user = usuario

        self.save(update_fields=["status"])

        status_anterior_norm = (status_anterior or "").upper()
        novo_status_norm = (novo_status_str or "").upper()
        gerar_documentos_automaticos_processo(self, status_anterior_norm, novo_status_norm)
        sincronizar_relacoes_apos_transicao(self, status_anterior_norm, novo_status_norm, usuario=usuario)
