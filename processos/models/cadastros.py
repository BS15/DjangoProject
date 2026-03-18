from django.db import models
from simple_history.models import HistoricalRecords


class Grupos(models.Model):
    grupo = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.grupo


class CargosFuncoes(models.Model):
    # O VÍNCULO PAI-FILHO:
    grupo = models.ForeignKey(
        'Grupos',
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


class ContasBancarias(models.Model):
    titular = models.ForeignKey('Credor', on_delete=models.CASCADE, null=True, blank=True, related_name='contas_bancarias')
    banco = models.CharField("Banco", max_length=50, blank=True, null=True)
    agencia = models.CharField("Agência", max_length=50, blank=True, null=True)
    conta = models.CharField("Conta", max_length=50, blank=True, null=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Titular: {self.titular} - Banco: {self.banco} - Ag: {self.agencia} / Cc: {self.conta}"


class Credor(models.Model):
    nome = models.CharField("Nome", max_length=50, null=True, blank=True)
    cpf_cnpj = models.CharField("CPF/CNPJ", max_length=50, null=True, blank=True)
    conta = models.ForeignKey('ContasBancarias', on_delete=models.PROTECT, blank=True, null=True, verbose_name="Conta Credor")
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


class DadosContribuinte(models.Model):
    cnpj = models.CharField(max_length=14)
    razao_social = models.CharField(max_length=255)
    tipo_inscricao = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.razao_social} ({self.cnpj})"

    class Meta:
        verbose_name = "Dados do Contribuinte"
        verbose_name_plural = "Dados do Contribuinte"
