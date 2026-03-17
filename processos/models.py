from django.db import models
from django.utils import timezone
from datetime import date
from simple_history.models import HistoricalRecords
from django.contrib.auth.models import User
#This file defines the models used in application.
#Processo model which represents payment process.
#DocumentoFiscal is model that represents fiscal note.

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

    # Se for documento de Verbas Indenizatórias
    if hasattr(instance, 'diaria') and instance.diaria:
        return f'verbas/diarias/diaria_{instance.diaria.id}/{filename}'

    if hasattr(instance, 'reembolso') and instance.reembolso:
        return f'verbas/reembolsos/reembolso_{instance.reembolso.id}/{filename}'

    if hasattr(instance, 'jeton') and instance.jeton:
        return f'verbas/jetons/jeton_{instance.jeton.id}/{filename}'

    if hasattr(instance, 'auxilio') and instance.auxilio:
        return f'verbas/auxilios/auxilio_{instance.auxilio.id}/{filename}'

    return f'documentos_avulsos/{filename}'

class CodigosImposto(models.Model):
    # This replaces your hard-coded choices
    codigo = models.CharField(max_length=10, unique=True, null=True, blank=True)

    FAMILIA_IMPOSTO_CHOICES = [
        ('INSS', 'Previdenciário (Série 2000)'),
        ('FEDERAL', 'Federal - IR/CSRF (Série 4000)'),
    ]
    familia = models.CharField(
        max_length=10,
        choices=FAMILIA_IMPOSTO_CHOICES,
        default='FEDERAL',
        blank=True,
    )

    REGRA_COMPETENCIA_CHOICES = [
        ('emissao', 'Pela Data de Emissão da NF'),
        ('pagamento', 'Pela Data de Pagamento'),
    ]
    regra_competencia = models.CharField(
        max_length=15,
        choices=REGRA_COMPETENCIA_CHOICES,
        default='emissao'
    )

    aliquota = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vencimento_padrao = models.PositiveIntegerField(default=1, help_text="Dia de Vencimento Padrão", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    natureza_rendimento = models.CharField(
        max_length=5,
        blank=True,
        null=True,
        verbose_name="Natureza do Rendimento (EFD-Reinf)",
        help_text="Código de 5 dígitos (Tabela 01 do SPED). Ex: 15001, 17001. Mapeia o código de receita para o XML."
    )

    def __str__(self):
        return f"{self.codigo}"

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

class StatusChoicesRetencoes(models.Model):
    # This replaces your hard-coded choices
    status_choice = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.status_choice}"

class StatusChoicesVerbasIndenizatorias(models.Model):
    # This replaces your hard-coded choices
    status_choice = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.status_choice}"

class StatusChoicesSuprimentoDeFundos(models.Model):
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

class ContasBancarias(models.Model):
    titular = models.CharField("Titular", max_length=50, blank=True, null=True)
    banco = models.CharField("Banco", max_length=50, blank=True, null=True)
    agencia = models.CharField("Agência", max_length=50, blank=True, null=True)
    conta = models.CharField("Conta", max_length=50, blank=True, null=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Titular: {self.titular} - Banco: {self.banco} - Ag: {self.agencia} / Cc: {self.conta}"

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

class TiposDeVerbasIndenizatorias(models.Model):
    # This replaces your hard-coded choices
    tipo_de_verba_indenizatoria = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tipo_de_verba_indenizatoria}"

class TiposDePendencias(models.Model):
    # This replaces your hard-coded choices
    tipo_de_pendencia = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tipo_de_pendencia}"

class MeiosDeTransporte(models.Model):
    meio_de_transporte = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.meio_de_transporte}"

class Grupos(models.Model):
    grupo = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.grupo

class CargosFuncoes(models.Model):
    # O VÍNCULO PAI-FILHO:
    grupo = models.ForeignKey(
        Grupos,
        on_delete=models.PROTECT,
        related_name='cargos',
        verbose_name="Grupo Relacionado"
    )
    cargo_funcao = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        # Garante que não existam dois cargos iguais dentro do mesmo grupo
        unique_together = ('grupo', 'cargo_funcao')
        verbose_name = "Cargo / Função"
        verbose_name_plural = "Cargos e Funções"

    def __str__(self):
        return f"{self.grupo} -> {self.cargo_funcao}"

class Credor(models.Model):
    nome = models.CharField("Nome", max_length=50, null=True, blank=True)
    cpf_cnpj = models.CharField("CPF/CNPJ", max_length=50, null=True, blank=True)
    conta = models.ForeignKey(ContasBancarias,on_delete=models.PROTECT, blank=True, null=True, verbose_name="Conta Credor")
    chave_pix = models.CharField("Chave PIX do credor", max_length=50, null=True, blank=True)
    grupo = models.ForeignKey('Grupos', on_delete=models.PROTECT, blank=True, null=True)
    cargo_funcao = models.ForeignKey('CargosFuncoes', on_delete=models.PROTECT, blank=True, null=True)
    #Dados de contato
    telefone = models.CharField("Telefone do credor", max_length=50, null=True, blank=True)
    email = models.CharField("Email do credor", max_length=50, null=True, blank=True)

    TIPO_PESSOA_CHOICES = [
        ('PF', 'Pessoa Física (CPF)'),
        ('PJ', 'Pessoa Jurídica (CNPJ)'),
        ('EX', 'Exterior / Outros'),  # Opcional, mas salva vidas no setor público
    ]

    # Substituímos o campo "tipo" antigo por este:
    tipo = models.CharField(
        "Tipo de Pessoa",
        max_length=2,
        choices=TIPO_PESSOA_CHOICES,
        default='PJ'  # Assume PJ como padrão, já que é o mais comum em notas de empenho
    )
    codigo_servico_padrao = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name="Cód. Serviço Padrão INSS (Tabela 06)",
        help_text="Ex: 100000001 (Limpeza). Será herdado automaticamente pelas Notas Fiscais deste credor."
    )
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.nome}"

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
    codigo_barras = models.CharField(max_length=100, blank=True, null=True)
    data_vencimento = models.DateField(blank=True, null=True)
    data_pagamento = models.DateField(blank=True, null=True)
    forma_pagamento = models.ForeignKey('FormasDePagamento', on_delete=models.PROTECT, blank=True, null=True)
    tipo_pagamento = models.ForeignKey('TiposDePagamento', on_delete=models.PROTECT, blank=True, null=True)
    observacao = models.CharField(max_length=200, blank=True, null=True)
    conta = models.ForeignKey(ContasBancarias,on_delete=models.PROTECT, blank=True, null=True, verbose_name="Conta Sacada")

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

class DocumentoBase(models.Model):
    arquivo = models.FileField(upload_to=caminho_documento)
    ordem = models.PositiveIntegerField(default=1, help_text="Ordem do arquivo")
    tipo = models.ForeignKey(TiposDeDocumento, on_delete=models.PROTECT)

    class Meta:
        abstract = True
        ordering = ['ordem']

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

# 3. DOCUMENTOS DAS VERBAS (Uma tabela separada para cada)
class DocumentoDiaria(DocumentoBase):
    diaria = models.ForeignKey('Diaria', on_delete=models.CASCADE, related_name='documentos')
    history = HistoricalRecords()

class DocumentoReembolso(DocumentoBase):
    reembolso = models.ForeignKey('ReembolsoCombustivel', on_delete=models.CASCADE, related_name='documentos')
    history = HistoricalRecords()

class DocumentoJeton(DocumentoBase):
    jeton = models.ForeignKey('Jeton', on_delete=models.CASCADE, related_name='documentos')
    history = HistoricalRecords()

class DocumentoAuxilio(DocumentoBase):
    auxilio = models.ForeignKey('AuxilioRepresentacao', on_delete=models.CASCADE, related_name='documentos')
    history = HistoricalRecords()

class DocumentoSuprimentoDeFundos(DocumentoBase):
    suprimento = models.ForeignKey('SuprimentoDeFundos', on_delete=models.CASCADE, related_name='documentos')
    history = HistoricalRecords()


def caminho_comprovante(instance, filename):
    if instance.processo_id:
        try:
            processo = instance.processo
            ano = processo.data_empenho.year if processo.data_empenho else date.today().year
            mes = processo.data_empenho.month if processo.data_empenho else date.today().month
            return f'pagamentos/{ano}/{mes:02d}/proc_{processo.id}/comprovantes/{filename}'
        except Exception:
            pass
    return f'comprovantes/{filename}'


class ComprovanteDePagamento(models.Model):
    processo = models.ForeignKey(
        'Processo',
        on_delete=models.CASCADE,
        related_name='comprovantes_pagamento',
        verbose_name="Processo"
    )
    numero_comprovante = models.CharField(
        "Número do Comprovante",
        max_length=100,
        null=True,
        blank=True
    )
    credor_nome = models.CharField(
        "Credor (Texto)",
        max_length=200,
        null=True,
        blank=True
    )
    valor_pago = models.DecimalField(
        "Valor Pago",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    data_pagamento = models.DateField("Data de Pagamento", null=True, blank=True)
    arquivo = models.FileField(
        "Arquivo do Comprovante",
        upload_to=caminho_comprovante,
        null=True,
        blank=True
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Comprovante de Pagamento"
        verbose_name_plural = "Comprovantes de Pagamento"

    def __str__(self):
        return f"Comprovante - {self.processo} - {self.credor_nome} - R$ {self.valor_pago}"


class DocumentoFiscal(models.Model):
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name='notas_fiscais')
    nome_emitente = models.ForeignKey('Credor', on_delete=models.PROTECT, blank=True, null=True)
    cnpj_emitente = models.CharField(max_length=20, blank=True) # Permitimos blank=True para o save() cuidar disso
    numero_nota_fiscal = models.CharField(max_length=50)
    documento_vinculado = models.OneToOneField(
        'DocumentoProcesso',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='nota_referente',
        verbose_name="Documento PDF da Nota"
    )
    data_emissao = models.DateField()
    valor_bruto = models.DecimalField(max_digits=12, decimal_places=2)
    valor_liquido = models.DecimalField(max_digits=12, decimal_places=2)
    fiscal_contrato = models.ForeignKey(
        'Credor', # Recomendado usar string ou a classe se já estiver definida acima
        on_delete=models.PROTECT,
        verbose_name="Fiscal do Contrato",
        related_name="fiscalizadas", # Adicionado para evitar conflito de nomes
        null=True,
        blank=True,
        limit_choices_to={'grupo__grupo': 'FUNCIONÁRIOS'}
    )
    atestada = models.BooleanField(default=False)
    serie_nota_fiscal = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Série"
    )
    codigo_servico_inss = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name="Cód. Serviço INSS (Tabela 06 Reinf)"
    )
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        # Se um emitente foi selecionado e o CNPJ está vazio (ou queremos sempre atualizar)
        if self.nome_emitente:
            self.cnpj_emitente = self.nome_emitente.cpf_cnpj
        # Smart Inheritance: auto-fill codigo_servico_inss from the credor's default if not set
        if not self.codigo_servico_inss and self.nome_emitente and self.nome_emitente.codigo_servico_padrao:
            self.codigo_servico_inss = self.nome_emitente.codigo_servico_padrao
        super().save(*args, **kwargs)

    def __str__(self):
        return f"NF {self.numero_nota_fiscal} - {self.nome_emitente}"

class Pendencia(models.Model):
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name='pendencias')
    status = models.ForeignKey('StatusChoicesPendencias', on_delete=models.PROTECT, blank=True, null=True)
    tipo = models.ForeignKey(TiposDePendencias, on_delete=models.PROTECT)
    descricao = models.CharField(max_length=200, blank=True, null=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"PENDÊNCIA: {self.tipo} - {self.descricao}"

class RetencaoImposto(models.Model):
    nota_fiscal = models.ForeignKey(DocumentoFiscal, on_delete=models.CASCADE, related_name='retencoes')
    beneficiario = models.ForeignKey('Credor', on_delete=models.PROTECT, blank=True, null=True, verbose_name="Beneficiário", related_name='retencoes')
    rendimento_tributavel = models.DecimalField("Base de Cálculo / Rend. Tributável", null=True, blank=True, max_digits=12, decimal_places=2)
    data_pagamento = models.DateField(blank=True, null=True)
    codigo = models.ForeignKey(CodigosImposto, on_delete=models.PROTECT)
    valor = models.DecimalField("Valor Retido", max_digits=12, decimal_places=2)
    status = models.ForeignKey('StatusChoicesRetencoes', on_delete=models.PROTECT, blank=True, null=True)

    competencia = models.DateField(
        "Mês de Competência",
        help_text="Salvo internamente como YYYY-MM-01, exibido como MM/AAAA",
        blank=True,
        null=True
    )

    def save(self, *args, **kwargs):
        # 1. Só calcula se os relacionamentos já existirem na memória
        if getattr(self, 'codigo', None) and getattr(self, 'nota_fiscal', None):
            data_base = None

            # 2. Avalia a regra do imposto (INSS, ISS = Emissão / IRRF, CSRF = Pagamento)
            if self.codigo.regra_competencia == 'emissao':
                data_base = self.nota_fiscal.data_emissao

            elif self.codigo.regra_competencia == 'pagamento':
                # Tenta pegar a data de pagamento da própria retenção.
                # Se estiver vazia, tenta puxar do Processo pai.
                data_base = self.data_pagamento or self.nota_fiscal.processo.data_pagamento

            # 3. Se encontrou uma data válida, "trava" no dia 1º daquele mês e ano
            if data_base:
                self.competencia = date(data_base.year, data_base.month, 1)

        # 4. Chama o salvamento original do Django para gravar no banco de dados
        super().save(*args, **kwargs)

    history = HistoricalRecords()

    def __str__(self):
        return f"{self.codigo} - R$ {self.valor}"

#Model for indenizatory payments - handles pendencies.
#Is "activated" when payment type is verbas indenizatórias.
#This should be for administrative handling.
#Doesn't relate immediately to payments.

class Diaria(models.Model):
    TIPO_SOLICITACAO = [
        ('INICIAL', 'Concessão Inicial'),
        ('PRORROGACAO', 'Prorrogação'),
        ('COMPLEMENTACAO', 'Complementação')
    ]

    processo = models.ForeignKey('Processo', on_delete=models.CASCADE, related_name='diarias', null=True, blank=True)
    numero_sequencial = models.CharField("Número Sequencial", max_length=50)
    beneficiario = models.ForeignKey('Credor', on_delete=models.PROTECT, limit_choices_to={'tipo': 'PF'},
                                     verbose_name="Beneficiário", related_name='diarias_como_beneficiario')
    proponente = models.ForeignKey('Credor', on_delete=models.PROTECT, limit_choices_to={'tipo': 'PF'},
                                   verbose_name="Proponente", related_name='diarias_como_proponente',
                                   null=True, blank=True)

    # Dados específicos da Diária
    tipo_solicitacao = models.CharField(max_length=20, choices=TIPO_SOLICITACAO, default='INICIAL')
    data_saida = models.DateField("Data de Saída")
    data_retorno = models.DateField("Data de Retorno")
    cidade_origem = models.CharField("Cidade de Origem", max_length=50)
    cidade_destino = models.CharField("Cidade(s) de Destino", max_length=100)
    objetivo = models.CharField("Objetivo da Viagem", max_length=200)

    quantidade_diarias = models.DecimalField("Quantidade de Diárias", max_digits=4, decimal_places=1)
    valor_total = models.DecimalField("Valor Total (R$)", max_digits=12, decimal_places=2, blank=True, null=True)
    meio_de_transporte = models.ForeignKey('MeiosDeTransporte', on_delete=models.PROTECT, blank=True, null=True,
                                           verbose_name="Meio de Transporte")
    status = models.ForeignKey('StatusChoicesVerbasIndenizatorias', on_delete=models.PROTECT, blank=True, null=True)
    autorizada = models.BooleanField("Autorizada", default=False)
    history = HistoricalRecords()

    def calcular_valor_total(self):
        """Returns the calculated valor_total based on beneficiario cargo_funcao unit value."""
        if not self.beneficiario_id or not self.quantidade_diarias:
            return None
        credor = self.beneficiario
        if not credor.cargo_funcao_id:
            return None
        valor_unitario = Tabela_Valores_Unitarios_Verbas_Indenizatorias.get_valor_para_cargo_diaria(credor.cargo_funcao)
        if valor_unitario is not None:
            return valor_unitario * self.quantidade_diarias
        return None

    def save(self, *args, **kwargs):
        calculado = self.calcular_valor_total()
        if calculado is not None:
            self.valor_total = calculado
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Diária {self.numero_sequencial} - {self.beneficiario}"

class ReembolsoCombustivel(models.Model):
    processo = models.ForeignKey('Processo', on_delete=models.CASCADE, related_name='reembolsos_combustivel', null=True,
                                 blank=True)
    diaria = models.ForeignKey('Diaria', on_delete=models.CASCADE, related_name='reembolsos_combustivel', null=True,
                               blank=True, verbose_name="Diária")
    numero_sequencial = models.CharField("Número Sequencial", max_length=50)
    beneficiario = models.ForeignKey('Credor', on_delete=models.PROTECT, limit_choices_to={'tipo': 'PF'},
                                     verbose_name="Beneficiário")

    data_saida = models.DateField("Data de Saída")
    data_retorno = models.DateField("Data de Retorno")
    cidade_origem = models.CharField("Cidade de Origem", max_length=50)
    cidade_destino = models.CharField("Cidade(s) de Destino", max_length=100)

    distancia_km = models.DecimalField("Distância Percorrida (KM)", max_digits=6, decimal_places=2)
    preco_combustivel = models.DecimalField("Preço Médio do Combustível (R$)", max_digits=5, decimal_places=2)

    valor_total = models.DecimalField("Valor do Reembolso (R$)", max_digits=12, decimal_places=2)
    objetivo = models.CharField("Objetivo", max_length=200, blank=True, null=True)
    status = models.ForeignKey('StatusChoicesVerbasIndenizatorias', on_delete=models.PROTECT, blank=True, null=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"Reembolso de Combustível: {self.numero_sequencial} - {self.beneficiario}"

class Jeton(models.Model):
    processo = models.ForeignKey('Processo', on_delete=models.CASCADE, related_name='jetons', null=True, blank=True)
    numero_sequencial = models.CharField("Número Sequencial", max_length=50)
    beneficiario = models.ForeignKey('Credor', on_delete=models.PROTECT, limit_choices_to={'tipo': 'PF'},
                                     verbose_name="Conselheiro(a)")

    # Dados específicos do Jeton
    reuniao = models.CharField("Reunião/Sessão de Referência", max_length=7)

    valor_total = models.DecimalField("Valor Total (R$)", max_digits=12, decimal_places=2)
    status = models.ForeignKey('StatusChoicesVerbasIndenizatorias', on_delete=models.PROTECT, blank=True, null=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"Jeton {self.mes_referencia} - {self.beneficiario}"

class AuxilioRepresentacao(models.Model):
    processo = models.ForeignKey('Processo', on_delete=models.CASCADE, related_name='auxilios_representacao', null=True,
                                 blank=True)
    numero_sequencial = models.CharField("Número Sequencial", max_length=50)
    beneficiario = models.ForeignKey('Credor', on_delete=models.PROTECT, limit_choices_to={'tipo': 'PF'},
                                     verbose_name="Beneficiário")

    # Dados específicos do Auxílio
    objetivo = models.CharField("Evento/Motivo da Representação", max_length=200, blank=True, null=True,
                                            help_text="Preencha se for representação em evento específico")

    valor_total = models.DecimalField("Valor Total (R$)", max_digits=12, decimal_places=2)
    status = models.ForeignKey('StatusChoicesVerbasIndenizatorias', on_delete=models.PROTECT, blank=True, null=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"Aux. Representação {self.numero_sequencial} - {self.beneficiario}"

class Tabela_Valores_Unitarios_Verbas_Indenizatorias(models.Model):
    tipo = models.ForeignKey(TiposDeVerbasIndenizatorias, on_delete=models.PROTECT, blank=True, null=True)
    cargo_funcao = models.ForeignKey('CargosFuncoes', on_delete=models.PROTECT, blank=True, null=True)
    valor_unitario = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2)

    @classmethod
    def get_valor_para_cargo_diaria(cls, cargo_funcao):
        """Returns the valor_unitario for the given cargo_funcao for diárias, or None if not found."""
        tabela = cls.objects.filter(
            cargo_funcao=cargo_funcao,
            tipo__tipo_de_verba_indenizatoria__icontains='diária'
        ).first()
        if not tabela:
            tabela = cls.objects.filter(cargo_funcao=cargo_funcao).first()
        if tabela and tabela.valor_unitario is not None:
            return tabela.valor_unitario
        return None

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
    suprimento = models.ForeignKey(SuprimentoDeFundos, on_delete=models.CASCADE, related_name='despesas')
    data = models.DateField("Data da Compra")
    estabelecimento = models.CharField("Estabelecimento (Credor)", max_length=150)
    cnpj_cpf = models.CharField("CNPJ/CPF", max_length=20, blank=True, null=True)
    detalhamento = models.CharField("Material/Serviço Adquirido", max_length=255)
    nota_fiscal = models.CharField("Nº Nota Fiscal/Cupom", max_length=50)
    valor = models.DecimalField("Valor Pago (R$)", max_digits=10, decimal_places=2)

    # NOVO CAMPO: O arquivo único contendo Solicitação + Nota Fiscal
    arquivo = models.FileField("Arquivo Único (Solicitação + NF)", upload_to=caminho_documento, blank=True, null=True)

    def __str__(self):
        return f"{self.data} - {self.estabelecimento} - R$ {self.valor}"
    history = HistoricalRecords()


STATUS_CONTINGENCIA = [
    ('PENDENTE_SUPERVISOR', 'Pendente Supervisor'),
    ('PENDENTE_ORDENADOR', 'Pendente Ordenador de Despesa'),
    ('PENDENTE_CONSELHO', 'Pendente Conselho Fiscal'),
    ('APROVADA', 'Aprovada'),
    ('REJEITADA', 'Rejeitada'),
]


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