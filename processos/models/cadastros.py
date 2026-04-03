"""Modelos cadastrais: credores, contas bancárias e contas fixas mensais."""

import datetime
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords


class CargosFuncoes(models.Model):
    """Catálogo de grupos e cargos/funções para classificação de credores."""

    grupo = models.CharField(max_length=100, verbose_name="Grupo Relacionado", blank=True, default='')
    cargo_funcao = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('grupo', 'cargo_funcao')
        verbose_name = "Cargo / Função"
        verbose_name_plural = "Cargos e Funções"

    def __str__(self):
        return f"{self.grupo} -> {self.cargo_funcao}"


class ContasBancarias(models.Model):
    """Conta bancária vinculável ao credor para pagamento e conciliação."""

    titular = models.ForeignKey('Credor', on_delete=models.CASCADE, null=True, blank=True, related_name='contas_bancarias')
    banco = models.CharField("Banco", max_length=50, blank=True, null=True)
    agencia = models.CharField("Agência", max_length=50, blank=True, null=True)
    conta = models.CharField("Conta", max_length=50, blank=True, null=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Titular: {self.titular} - Banco: {self.banco} - Ag: {self.agencia} / Cc: {self.conta}"


class Credor(models.Model):
    """Entidade favorecida em pagamentos, verbas e retenções."""

    nome = models.CharField("Nome", max_length=50, null=True, blank=True)
    cpf_cnpj = models.CharField("CPF/CNPJ", max_length=50, null=True, blank=True)
    conta = models.ForeignKey('ContasBancarias', on_delete=models.PROTECT, blank=True, null=True, verbose_name="Conta Credor")
    chave_pix = models.CharField("Chave PIX do credor", max_length=50, null=True, blank=True)
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


class DadosContribuinte(models.Model):
    """Identificação fiscal do órgão para filtros e integrações tributárias."""

    cnpj = models.CharField(max_length=14)
    razao_social = models.CharField(max_length=255)
    tipo_inscricao = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.razao_social} ({self.cnpj})"

    class Meta:
        verbose_name = "Dados do Contribuinte"
        verbose_name_plural = "Dados do Contribuinte"


class ContaFixa(models.Model):
    """Configuração de despesa recorrente que gera faturas mensais."""

    credor = models.ForeignKey(
        'Credor',
        on_delete=models.PROTECT,
        verbose_name="Credor/Fornecedor"
    )
    referencia = models.CharField(
        "Referência / Descrição",
        max_length=200,
        help_text="Ex: Conta de Luz - Sede"
    )
    dia_vencimento = models.IntegerField(
        "Dia Padrão de Vencimento",
        validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    ativa = models.BooleanField("Conta Ativa", default=True)
    data_inicio = models.DateField(
        "Data de Início",
        default=datetime.date.today,
        help_text="Mês a partir do qual as faturas mensais serão geradas."
    )

    class Meta:
        verbose_name = "Conta Fixa"
        verbose_name_plural = "Contas Fixas"

    def __str__(self):
        return f"{self.credor.nome} - {self.referencia}"


class FaturaMensal(models.Model):
    """Fatura de referência mensal derivada de uma conta fixa."""

    conta_fixa = models.ForeignKey(
        ContaFixa,
        on_delete=models.CASCADE,
        related_name='faturas'
    )
    mes_referencia = models.DateField("Mês de Referência")
    processo_vinculado = models.ForeignKey(
        'Processo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='faturas_vinculadas'
    )

    class Meta:
        verbose_name = "Fatura Mensal"
        verbose_name_plural = "Faturas Mensais"
        unique_together = ('conta_fixa', 'mes_referencia')

    def __str__(self):
        return f"{self.conta_fixa} - {self.mes_referencia.strftime('%m/%Y')}"

    @property
    def data_vencimento_exata(self):
        """Calcula a data de vencimento respeitando o último dia do mês."""
        import calendar
        dia = self.conta_fixa.dia_vencimento
        ultimo_dia = calendar.monthrange(self.mes_referencia.year, self.mes_referencia.month)[1]
        dia_efetivo = min(dia, ultimo_dia)
        return self.mes_referencia.replace(day=dia_efetivo)

    @property
    def status(self):
        """Retorna estado operacional da fatura: pendente, em andamento ou pago."""
        if not self.processo_vinculado:
            return 'PENDENTE'
        if self.processo_vinculado.status and 'PAGO' in self.processo_vinculado.status.status_choice.upper():
            return 'PAGO'
        return 'EM ANDAMENTO'
