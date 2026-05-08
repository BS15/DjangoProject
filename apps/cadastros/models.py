"""Modelos cadastrais: credores, contas bancárias e contas fixas mensais."""

import datetime
import re
from django.core.validators import MaxValueValidator, MinValueValidator, EmailValidator
from django.db import models
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords

from commons.shared.field_validators import validar_cpf_cnpj


class CargosFuncoes(models.Model):
    """Catálogo de grupos e cargos/funções para classificação de credores."""

    grupo = models.CharField(max_length=100, verbose_name="Grupo Relacionado", blank=True, default='')
    cargo_funcao = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    history = HistoricalRecords()

    class Meta:
        unique_together = ('grupo', 'cargo_funcao')
        verbose_name = "Cargo / Função"
        verbose_name_plural = "Cargos e Funções"

    def __str__(self):
        """Retorna representação textual do cargo/função com grupo."""
        return f"{self.grupo} -> {self.cargo_funcao}"


class ContasBancarias(models.Model):
    """Conta bancária vinculável ao credor para pagamento e conciliação."""

    titular = models.ForeignKey('Credor', on_delete=models.CASCADE, null=True, blank=True, related_name='contas_bancarias')
    banco = models.CharField("Banco", max_length=50, blank=True, null=True)
    agencia = models.CharField("Agência", max_length=50, blank=True, null=True)
    conta = models.CharField("Conta", max_length=50, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    history = HistoricalRecords()

    def __str__(self):
        """Retorna representação textual da conta bancária com titular, banco e agência."""
        return f"Titular: {self.titular} - Banco: {self.banco} - Ag: {self.agencia} / Cc: {self.conta}"


class Credor(models.Model):
    """Entidade favorecida em pagamentos, verbas e retenções."""

    nome = models.CharField("Nome", max_length=50, null=False, blank=False)
    cpf_cnpj = models.CharField("CPF/CNPJ", max_length=50, null=False, blank=False, validators=[validar_cpf_cnpj])
    usuario = models.OneToOneField(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='credor_vinculado', verbose_name="Usuário do Portal"
    )
    conta = models.ForeignKey('ContasBancarias', on_delete=models.PROTECT, blank=True, null=True, verbose_name="Conta Credor")
    chave_pix = models.CharField("Chave PIX do credor", max_length=50, null=True, blank=True)
    cargo_funcao = models.ForeignKey('CargosFuncoes', on_delete=models.PROTECT, blank=True, null=True)
    telefone = models.CharField("Telefone do credor", max_length=20, null=True, blank=True)
    email = models.EmailField("Email do credor", max_length=254, null=True, blank=True)

    TIPO_PESSOA_CHOICES = [
        ('PF', 'Pessoa Física (CPF)'),
        ('PJ', 'Pessoa Jurídica (CNPJ)'),
        ('EX', 'Exterior / Outros'),
    ]

    tipo = models.CharField(
        "Tipo de Pessoa",
        max_length=2,
        choices=TIPO_PESSOA_CHOICES,
        default='PJ'
    )
    codigo_servico_padrao = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name="Cód. Serviço Padrão INSS (Tabela 06)",
        help_text="Ex: 100000001 (Limpeza). Será herdado automaticamente pelas Notas Fiscais deste credor."
    )
    is_entidade_imune = models.BooleanField(
        "Entidade Imune/Isenta (EFD-Reinf)",
        default=False,
        help_text="Marque se a entidade é legalmente imune/isenta de tributação (ex: entidades públicas, igrejas, ONGs)."
    )
    ativo = models.BooleanField("Credor Ativo", default=True)
    history = HistoricalRecords()

    def __str__(self):
        """Retorna o nome do credor como representação textual."""
        return f"{self.nome}"

    def clean(self):
        """Garante consistência entre tipo de pessoa e documento informado."""
        super().clean()
        documento = re.sub(r'\D', '', self.cpf_cnpj or '')

        if self.tipo == 'PF' and len(documento) != 11:
            raise ValidationError({'cpf_cnpj': 'Para Pessoa Física, informe um CPF com 11 dígitos.'})

        if self.tipo == 'PJ' and len(documento) != 14:
            raise ValidationError({'cpf_cnpj': 'Para Pessoa Jurídica, informe um CNPJ com 14 dígitos.'})



# Modelo DadosContribuinte migrado para fiscal.models


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
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Conta Fixa"
        verbose_name_plural = "Contas Fixas"

    def __str__(self):
        """Retorna descrição da conta fixa com nome do credor e referência."""
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
        'pagamentos.Processo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='faturas_vinculadas'
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Fatura Mensal"
        verbose_name_plural = "Faturas Mensais"
        unique_together = ('conta_fixa', 'mes_referencia')

    def __str__(self):
        """Retorna representação textual da fatura com conta fixa e mês de referência."""
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
        if self.processo_vinculado.status and 'PAGO' in self.processo_vinculado.status.opcao_status.upper():
            return 'PAGO'
        return 'EM ANDAMENTO'


def gerar_faturas_do_mes(ano, mes):
    """Gera faturas mensais para contas ativas na competência informada."""
    import datetime
    from django.db.models import Q

    data_ref = datetime.date(ano, mes, 1)
    contas_ativas = ContaFixa.objects.filter(ativa=True).filter(
        Q(data_inicio__year__lt=ano) | Q(data_inicio__year=ano, data_inicio__month__lte=mes)
    )
    for conta in contas_ativas:
        FaturaMensal.objects.get_or_create(conta_fixa=conta, mes_referencia=data_ref)
