from django.db import models
from datetime import date
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords
from processos.validators import validar_arquivo_seguro


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


class CodigosImposto(models.Model):
    # This replaces your hard-coded choices
    codigo = models.CharField(max_length=10, unique=True, null=True, blank=True)

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
    is_active = models.BooleanField(default=True)
    natureza_rendimento = models.CharField(
        max_length=5,
        blank=True,
        null=True,
        verbose_name="Natureza do Rendimento (EFD-Reinf)",
        help_text="Código de 5 dígitos (Tabela 01 do SPED). Ex: 15001, 17001. Mapeia o código de receita para o XML."
    )

    SERIE_REINF_CHOICES = [
        ('NONE', 'Não mapeado'),
        ('S2000', 'Série 2000 – Previdenciário (INSS)'),
        ('S4000', 'Série 4000 – Retenções Federais (IRRF/CSRF)'),
    ]
    serie_reinf = models.CharField(
        max_length=6,
        choices=SERIE_REINF_CHOICES,
        default='NONE',
        verbose_name="Série EFD-Reinf",
        help_text="Classifica o imposto para geração do XML EFD-Reinf: S2000 = INSS, S4000 = IR/CSLL/PIS/COFINS."
    )

    def __str__(self):
        return f"{self.codigo}"


class StatusChoicesRetencoes(models.Model):
    # This replaces your hard-coded choices
    status_choice = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.status_choice}"


class DocumentoFiscal(models.Model):
    processo = models.ForeignKey('Processo', on_delete=models.CASCADE, related_name='notas_fiscais')
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
        User,
        on_delete=models.SET_NULL,
        verbose_name="Fiscal do Contrato",
        related_name='notas_fiscalizadas',
        null=True,
        blank=True,
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


class RetencaoImposto(models.Model):
    nota_fiscal = models.ForeignKey('DocumentoFiscal', on_delete=models.CASCADE, related_name='retencoes')
    beneficiario = models.ForeignKey('Credor', on_delete=models.PROTECT, blank=True, null=True, verbose_name="Beneficiário", related_name='retencoes')
    rendimento_tributavel = models.DecimalField("Base de Cálculo / Rend. Tributável", null=True, blank=True, max_digits=12, decimal_places=2)
    data_pagamento = models.DateField(blank=True, null=True)
    codigo = models.ForeignKey('CodigosImposto', on_delete=models.PROTECT)
    valor = models.DecimalField("Valor Retido", max_digits=12, decimal_places=2)
    status = models.ForeignKey('StatusChoicesRetencoes', on_delete=models.PROTECT, blank=True, null=True)
    processo_pagamento = models.ForeignKey(
        'Processo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='impostos_recolhidos',
        verbose_name="Processo de Recolhimento",
        help_text="O Processo agrupado gerado para pagar esta retenção ao órgão arrecadador."
    )

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
        blank=True,
        validators=[validar_arquivo_seguro]
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Comprovante de Pagamento"
        verbose_name_plural = "Comprovantes de Pagamento"

    def __str__(self):
        return f"Comprovante - {self.processo} - {self.credor_nome} - R$ {self.valor_pago}"
