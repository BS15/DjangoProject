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



class StatusProcesso(models.TextChoices):
    """Estados canônicos do fluxo de pagamento usados nas regras de domínio."""
    CANCELADO_ANULADO = "CANCELADO / ANULADO", "Cancelado / Anulado"
    A_EMPENHAR = "A EMPENHAR", "A Empenhar"
    AGUARDANDO_LIQUIDACAO = "AGUARDANDO LIQUIDAÇÃO", "Aguardando Liquidação"
    A_PAGAR_PENDENTE_AUTORIZACAO = "A PAGAR - PENDENTE AUTORIZAÇÃO", "A Pagar - Pendente Autorização"
    A_PAGAR_ENVIADO_PARA_AUTORIZACAO = "A PAGAR - ENVIADO PARA AUTORIZAÇÃO", "A Pagar - Enviado para Autorização"
    A_PAGAR_AUTORIZADO = "A PAGAR - AUTORIZADO", "A Pagar - Autorizado"
    LANCADO_AGUARDANDO_COMPROVANTE = "LANÇADO - AGUARDANDO COMPROVANTE", "Lançado - Aguardando Comprovante"
    PAGO_EM_CONFERENCIA = "PAGO - EM CONFERÊNCIA", "Pago - Em Conferência"
    PAGO_A_CONTABILIZAR = "PAGO - A CONTABILIZAR", "Pago - A Contabilizar"
    # PAGO_EM_CONTABILIZACAO removed (dead status)
    CONTABILIZADO_CONSELHO = (
        "CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL",
        "Contabilizado - Conselho Fiscal",
    )
    APROVADO_PENDENTE_ARQUIVAMENTO = "APROVADO - PENDENTE ARQUIVAMENTO", "Aprovado - Pendente Arquivamento"
    ARQUIVADO = "ARQUIVADO", "Arquivado"


STATUS_PROCESSO_BLOQUEADOS_TOTAL = (
    StatusProcesso.CANCELADO_ANULADO,
    StatusProcesso.ARQUIVADO,
    StatusProcesso.APROVADO_PENDENTE_ARQUIVAMENTO,
    StatusProcesso.CONTABILIZADO_CONSELHO,
)

STATUS_PROCESSO_SOMENTE_DOCUMENTOS = (
    StatusProcesso.LANCADO_AGUARDANDO_COMPROVANTE,
    StatusProcesso.PAGO_EM_CONFERENCIA,
    StatusProcesso.A_PAGAR_AUTORIZADO,
    StatusProcesso.A_PAGAR_ENVIADO_PARA_AUTORIZACAO,
)

STATUS_PROCESSO_BLOQUEADOS_FORM = (
    *STATUS_PROCESSO_BLOQUEADOS_TOTAL,
    *STATUS_PROCESSO_SOMENTE_DOCUMENTOS,
    StatusProcesso.PAGO_A_CONTABILIZAR,
)

STATUS_PROCESSO_CONTAS_A_PAGAR = (
    StatusProcesso.A_PAGAR_PENDENTE_AUTORIZACAO,
    StatusProcesso.A_PAGAR_ENVIADO_PARA_AUTORIZACAO,
    StatusProcesso.A_PAGAR_AUTORIZADO,
    StatusProcesso.LANCADO_AGUARDANDO_COMPROVANTE,
)

STATUS_PROCESSO_PAGOS = (
    StatusProcesso.PAGO_EM_CONFERENCIA,
    StatusProcesso.PAGO_A_CONTABILIZAR,
)

STATUS_PROCESSO_PAGOS_E_POSTERIORES = (
    *STATUS_PROCESSO_PAGOS,
    StatusProcesso.CONTABILIZADO_CONSELHO,
    StatusProcesso.APROVADO_PENDENTE_ARQUIVAMENTO,
    StatusProcesso.ARQUIVADO,
)

STATUS_PROCESSO_PRE_AUTORIZACAO = (
    StatusProcesso.A_EMPENHAR,
    StatusProcesso.AGUARDANDO_LIQUIDACAO,
    StatusProcesso.A_PAGAR_PENDENTE_AUTORIZACAO,
    StatusProcesso.A_PAGAR_ENVIADO_PARA_AUTORIZACAO,
)

# Aliases legados para módulos ainda não migrados.
ProcessoStatus = StatusProcesso
PROCESSO_STATUS_BLOQUEADOS_TOTAL = STATUS_PROCESSO_BLOQUEADOS_TOTAL
PROCESSO_STATUS_SOMENTE_DOCUMENTOS = STATUS_PROCESSO_SOMENTE_DOCUMENTOS
PROCESSO_STATUS_BLOQUEADOS_FORM = STATUS_PROCESSO_BLOQUEADOS_FORM
PROCESSO_STATUS_CONTAS_A_PAGAR = STATUS_PROCESSO_CONTAS_A_PAGAR
PROCESSO_STATUS_PAGOS = STATUS_PROCESSO_PAGOS
PROCESSO_STATUS_PAGOS_E_POSTERIORES = STATUS_PROCESSO_PAGOS_E_POSTERIORES
PROCESSO_STATUS_PRE_AUTORIZACAO = STATUS_PROCESSO_PRE_AUTORIZACAO



class StatusReuniaoConselho(models.TextChoices):
    """Estados da reunião de conselho fiscal."""
    AGENDADA = "AGENDADA", "Agendada/Em Montagem"
    EM_ANALISE = "EM_ANALISE", "Em Análise pelo Conselho"
    CONCLUIDA = "CONCLUIDA", "Concluída"



class ReuniaoConselhoFiscal(models.Model):
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
        choices=StatusReuniaoConselho.choices,
        default=StatusReuniaoConselho.AGENDADA,
    )
    class Meta:
        verbose_name = "Reunião do Conselho"
        verbose_name_plural = "Reuniões do Conselho"
        ordering = ["-numero"]
    def __str__(self):
        return f"{self.numero}ª Reunião - {self.trimestre_referencia}"



class GerenciadorProcesso(models.Manager):
    """Gerenciador com compatibilidade para kwargs legados de empenho."""
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
    forma_pagamento = models.ForeignKey("pagamentos.FormasPagamento", on_delete=models.PROTECT, blank=False, null=False)
    tipo_pagamento = models.ForeignKey("pagamentos.TiposPagamento", on_delete=models.PROTECT, blank=False, null=False)
    observacao = models.CharField(max_length=200, blank=True, null=True)
    conta = models.ForeignKey(
        "credores.ContasBancarias",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processos_sacados",
        verbose_name="Conta Sacada",
    )
    status = models.ForeignKey("pagamentos.StatusOpcoesProcesso", on_delete=models.PROTECT, blank=False, null=False)
    detalhamento = models.CharField(max_length=200, blank=True, null=True)
    tag = models.ForeignKey("pagamentos.OpcoesEtiqueta", on_delete=models.PROTECT, blank=True, null=True)
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
        "pagamentos.ReuniaoConselhoFiscal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processos_em_pauta",
        verbose_name="Reunião do Conselho",
    )
    history = HistoricalRecords()
    objects = GerenciadorProcesso()
    _CAMPOS_SENSIVEIS_POS_PAGAMENTO = {
        "credor_id",
        "valor_bruto",
        "valor_liquido",
        "data_vencimento",
        "data_pagamento",
        "forma_pagamento_id",
        "tipo_pagamento_id",
        "observacao",
        "detalhamento",
        "conta_id",
        "tag_id",
        "n_pagamento_siscac",
    }

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
            if not atual or not getattr(atual, "arquivo", None) or not getattr(atual, "tipo", None):
                raise ValidationError(
                    "DocumentoOrcamentario exige arquivo e tipo obrigatórios. "
                    "Cadastre o documento orçamentário completo antes de atualizar metadados de empenho."
                )

            from pagamentos.domain_models.documentos import DocumentoOrcamentario

            DocumentoOrcamentario.objects.create(
                processo=self,
                arquivo=atual.arquivo,
                tipo=atual.tipo,
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
        from pagamentos.domain_models.documentos import DocumentoOrcamentario

        if isinstance(data_empenho, str):
            data_empenho = datetime.strptime(data_empenho, "%Y-%m-%d").date()

        if data_empenho and not ano_exercicio:
            ano_exercicio = data_empenho.year

        if not any(value not in (None, "") for value in (numero_nota_empenho, data_empenho, ano_exercicio)):
            return None

        atual = self.documento_orcamentario_principal
        if not atual or not getattr(atual, "arquivo", None) or not getattr(atual, "tipo", None):
            raise ValidationError(
                "DocumentoOrcamentario exige arquivo e tipo obrigatórios. "
                "Cadastre o documento orçamentário completo antes de registrar metadados de empenho."
            )

        return DocumentoOrcamentario.objects.create(
            processo=self,
            arquivo=atual.arquivo,
            tipo=atual.tipo,
            numero_nota_empenho=numero_nota_empenho,
            data_empenho=data_empenho,
            ano_exercicio=ano_exercicio,
        )

    def save(self, *args, **kwargs):
        self._enforce_domain_seal(update_fields=kwargs.get("update_fields"))
        super().save(*args, **kwargs)
        self._persist_pending_documento_orcamentario()

    def _enforce_domain_seal(self, update_fields=None):
        """Bloqueia mutação direta de campos sensíveis após pagamento.

        A regra impede bypass por payload direto em scripts/API quando o processo
        já está em estágios pós-pagamento, exceto em fluxos autorizados
        (contingência explícita via `_bypass_domain_seal` ou processo em contingência).
        """
        if not self.pk:
            return

        if getattr(self, "_bypass_domain_seal", False):
            return

        if self.em_contingencia:
            return

        status_atual = (self.status.opcao_status or "").upper() if self.status else ""
        if status_atual not in STATUS_PROCESSO_PAGOS_E_POSTERIORES:
            return

        original = type(self).objects.get(pk=self.pk)
        campos_sensiveis = self._CAMPOS_SENSIVEIS_POS_PAGAMENTO

        if update_fields is not None:
            campos_avaliados = set(update_fields) & campos_sensiveis
        else:
            campos_avaliados = campos_sensiveis

        alterados = [
            campo for campo in campos_avaliados if getattr(self, campo) != getattr(original, campo)
        ]

        if alterados:
            raise ValidationError(
                {
                    "status": (
                        "Mutação direta bloqueada: alterações de dados financeiros/cadastrais "
                        "em estágios pós-pagamento devem ocorrer via contingência aprovada."
                    )
                }
            )

    def clean(self):
        """Valida integridade dos dados do processo antes de salvar."""
        errors = {}

        if self.valor_liquido and self.valor_bruto and self.valor_liquido > self.valor_bruto:
            errors["valor_liquido"] = "Valor líquido não pode ser maior que o valor bruto."

        if self.data_pagamento and self.data_vencimento and self.data_vencimento < self.data_pagamento:
            errors["data_vencimento"] = "Data de vencimento não pode ser anterior à data de pagamento."

        if not self.credor_id:
            errors["credor"] = "Credor é obrigatório."

        if not self.forma_pagamento_id:
            errors["forma_pagamento"] = "Forma de pagamento é obrigatória."

        if not self.tipo_pagamento_id:
            errors["tipo_pagamento"] = "Tipo de pagamento é obrigatório."

        # No fluxo de criação, o status inicial é definido na camada de ação
        # logo após a validação do formulário (mutator em add_process_action).
        # Para instâncias já persistidas, o status continua obrigatório.
        if self.pk and not self.status_id:
            errors["status"] = "Status é obrigatório."

        if errors:
            raise ValidationError(errors)

    @property
    def valor_efetivo(self):
        """Retorna valor líquido descontado das devoluções registradas."""
        total_devolvido = self.devolucoes.aggregate(total=Sum("valor_devolvido"))["total"] or 0
        return self.valor_liquido - total_devolvido

    def _atribuir_status_manual(self, nome_status):
        """Atribui um status diretamente ao processo sem executar turnpike."""
        from pagamentos.domain_models.catalogos import StatusOpcoesProcesso

        status_obj, _ = StatusOpcoesProcesso.objects.get_or_create(
            opcao_status__iexact=nome_status,
            defaults={"opcao_status": nome_status},
        )
        self.status = status_obj

    def definir_status_inicial(self, trigger_a_empenhar):
        """Configura o status inicial do processo durante o cadastro."""
        nome_status = (
            ProcessoStatus.A_EMPENHAR if trigger_a_empenhar else ProcessoStatus.A_PAGAR_PENDENTE_AUTORIZACAO
        )
        self._atribuir_status_manual(nome_status)

    def converter_para_extraorcamentario(self, confirmar=False):
        """Reclassifica o processo para extraorçamentário quando cabível."""
        status_atual = (self.status.opcao_status or "").upper() if self.status else ""
        if confirmar and status_atual == ProcessoStatus.A_EMPENHAR:
            self._atribuir_status_manual(ProcessoStatus.A_PAGAR_PENDENTE_AUTORIZACAO)
            self.extraorcamentario = True

    def avancar_status(self, novo_status_str, usuario=None):
        """Avança status validando turnpike e delega integrações aos serviços."""
        from pagamentos.domain_models.catalogos import StatusOpcoesProcesso
        from pagamentos.services.integracoes.processo_relacionados import sincronizar_relacoes_apos_transicao
        from pagamentos.services.processo_documentos import gerar_documentos_automaticos_processo
        from pagamentos.validators import verificar_turnpike

        status_anterior = self.status.opcao_status if self.status else ""
        erros = verificar_turnpike(self, status_anterior, novo_status_str)
        if erros:
            raise ValidationError(erros)

        novo_status, _ = StatusOpcoesProcesso.objects.get_or_create(
            opcao_status__iexact=novo_status_str,
            defaults={"opcao_status": novo_status_str},
        )
        self.status = novo_status

        if usuario:
            self._history_user = usuario

        self.save(update_fields=["status"])

        status_anterior_norm = (status_anterior or "").upper()
        novo_status_norm = (novo_status_str or "").upper()
        gerar_documentos_automaticos_processo(self, status_anterior_norm, novo_status_norm)
        sincronizar_relacoes_apos_transicao(self, status_anterior_norm, novo_status_norm, usuario=usuario)
