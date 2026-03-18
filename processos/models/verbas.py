from django.db import models
from simple_history.models import HistoricalRecords

from .fluxo import DocumentoBase, caminho_documento


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


class MeiosDeTransporte(models.Model):
    meio_de_transporte = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.meio_de_transporte}"


class TiposDeVerbasIndenizatorias(models.Model):
    # This replaces your hard-coded choices
    tipo_de_verba_indenizatoria = models.CharField(max_length=100, unique=True)

    # Pro-tip for administrative systems: Never delete tax codes, just deactivate them.
    # This prevents old invoices from breaking if a code is retired.
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tipo_de_verba_indenizatoria}"


class Tabela_Valores_Unitarios_Verbas_Indenizatorias(models.Model):
    tipo = models.ForeignKey('TiposDeVerbasIndenizatorias', on_delete=models.PROTECT, blank=True, null=True)
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


# 3. DOCUMENTOS DAS VERBAS (Uma tabela separada para cada)
class DocumentoDiaria(DocumentoBase):
    diaria = models.ForeignKey('Diaria', on_delete=models.CASCADE, related_name='documentos')
    history = HistoricalRecords()


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


class DocumentoReembolso(DocumentoBase):
    reembolso = models.ForeignKey('ReembolsoCombustivel', on_delete=models.CASCADE, related_name='documentos')
    history = HistoricalRecords()


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
        return f"Jeton {self.reuniao} - {self.beneficiario}"


class DocumentoJeton(DocumentoBase):
    jeton = models.ForeignKey('Jeton', on_delete=models.CASCADE, related_name='documentos')
    history = HistoricalRecords()


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


class DocumentoAuxilio(DocumentoBase):
    auxilio = models.ForeignKey('AuxilioRepresentacao', on_delete=models.CASCADE, related_name='documentos')
    history = HistoricalRecords()


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
    suprimento = models.ForeignKey('SuprimentoDeFundos', on_delete=models.CASCADE, related_name='despesas')
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


class DocumentoSuprimentoDeFundos(DocumentoBase):
    suprimento = models.ForeignKey('SuprimentoDeFundos', on_delete=models.CASCADE, related_name='documentos')
    history = HistoricalRecords()
