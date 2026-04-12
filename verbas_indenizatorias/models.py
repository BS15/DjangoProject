"""Modelos de verbas indenizatórias e seus documentos comprobatórios.

Este módulo define modelos para controle de diárias, reembolsos, jetons, auxílios e documentos comprobatórios de verbas indenizatórias.
"""

from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from simple_history.models import HistoricalRecords
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError as DjangoValidationError

from commons.shared.models import DocumentoBase
from commons.shared.storage_utils import caminho_documento, _delete_file


class StatusChoicesVerbasIndenizatorias(models.Model):
    """Catálogo de estados de verbas indenizatórias."""

    status_choice = models.CharField(max_length=100, unique=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.status_choice}"


class MeiosDeTransporte(models.Model):
    """Tabela de meios de transporte utilizados em diárias."""

    meio_de_transporte = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.meio_de_transporte}"


class TiposDeVerbasIndenizatorias(models.Model):
    """Tipos de verba indenizatória suportados pelo sistema."""

    tipo_de_verba_indenizatoria = models.CharField(max_length=100, unique=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tipo_de_verba_indenizatoria}"


class Tabela_Valores_Unitarios_Verbas_Indenizatorias(models.Model):
    """Tabela de valores unitários por tipo de verba e cargo/função."""

    tipo = models.ForeignKey('TiposDeVerbasIndenizatorias', on_delete=models.PROTECT, blank=True, null=True)
    cargo_funcao = models.ForeignKey('credores.CargosFuncoes', on_delete=models.PROTECT, blank=True, null=True)
    valor_unitario = models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2)

    @classmethod
    def get_valor_para_cargo_diaria(cls, cargo_funcao):
        """Obtém o valor unitário de diária para o cargo/função informado."""
        tabela = cls.objects.filter(
            cargo_funcao=cargo_funcao,
            tipo__tipo_de_verba_indenizatoria__icontains='diária'
        ).first()
        if not tabela:
            tabela = cls.objects.filter(cargo_funcao=cargo_funcao).first()
        if tabela and tabela.valor_unitario is not None:
            return tabela.valor_unitario
        return None


class Diaria(models.Model):
    """Solicitação/execução de diária com cálculo automático de valor."""

    TIPO_SOLICITACAO = [
        ('INICIAL', 'Concessão Inicial'),
        ('PRORROGACAO', 'Prorrogação'),
        ('COMPLEMENTACAO', 'Complementação')
    ]

    processo = models.ForeignKey('fluxo.Processo', on_delete=models.CASCADE, related_name='diarias', null=True, blank=True)
    beneficiario = models.ForeignKey('credores.Credor', on_delete=models.PROTECT, limit_choices_to={'tipo': 'PF'},
                                     verbose_name="Beneficiário", related_name='diarias_como_beneficiario')
    proponente = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='diarias_propostas', verbose_name="Proponente")

    tipo_solicitacao = models.CharField(max_length=20, choices=TIPO_SOLICITACAO, default='INICIAL')
    data_saida = models.DateField("Data de Saída")
    data_retorno = models.DateField("Data de Retorno")
    cidade_origem = models.CharField("Cidade de Origem", max_length=50)
    cidade_destino = models.CharField("Cidade(s) de Destino", max_length=100)
    objetivo = models.CharField("Objetivo da Viagem", max_length=200)

    quantidade_diarias = models.DecimalField("Quantidade de Diárias", max_digits=4, decimal_places=1, validators=[MinValueValidator(0.1)])
    valor_total = models.DecimalField("Valor Total (R$)", max_digits=12, decimal_places=2, blank=True, null=True)
    meio_de_transporte = models.ForeignKey('MeiosDeTransporte', on_delete=models.PROTECT, blank=True, null=True,
                                           verbose_name="Meio de Transporte")
    status = models.ForeignKey('StatusChoicesVerbasIndenizatorias', on_delete=models.PROTECT, blank=True, null=True)
    autorizada = models.BooleanField("Autorizada", default=False)
    numero_siscac = models.CharField("Nº SISCAC", max_length=20, unique=True, null=True, blank=True)

    assinaturas_autentique = GenericRelation('fluxo.AssinaturaAutentique')

    history = HistoricalRecords()

    def clean(self):
        """Valida que data_retorno é posterior ou igual a data_saida."""
        errors = {}

        if self.data_retorno and self.data_saida:
            if self.data_retorno < self.data_saida:
                errors['data_retorno'] = 'Data de retorno não pode ser anterior à data de saída.'

        if errors:
            raise DjangoValidationError(errors)

    def calcular_valor_total(self):
        """Calcula o valor total da diária conforme cargo/função do beneficiário."""
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
        """Atualiza valor total calculado antes da persistência."""
        calculado = self.calcular_valor_total()
        if calculado is not None:
            self.valor_total = calculado
        super().save(*args, **kwargs)

    def avancar_status(self, novo_status_str):
        """Avança status da diária com validação de turnpike específico."""
        from django.core.exceptions import ValidationError
        from fluxo.validators import verificar_turnpike_diaria

        status_anterior = self.status.status_choice if self.status else ''
        erros = verificar_turnpike_diaria(self, status_anterior, novo_status_str)

        if erros:
            raise ValidationError(' '.join(erros))

        novo_status, _ = StatusChoicesVerbasIndenizatorias.objects.get_or_create(
            status_choice__iexact=novo_status_str,
            defaults={'status_choice': novo_status_str}
        )
        self.status = novo_status
        self.save(update_fields=['status'])

    def __str__(self):
        return f"Diária {self.numero_siscac} - {self.beneficiario}"


class DocumentoDiaria(DocumentoBase):
    """Documento comprobatório associado a diária."""

    diaria = models.ForeignKey('Diaria', on_delete=models.CASCADE, related_name='documentos')
    history = HistoricalRecords()


class ReembolsoCombustivel(models.Model):
    """Registro de reembolso de combustível vinculado a diária/processo."""

    processo = models.ForeignKey('fluxo.Processo', on_delete=models.CASCADE, related_name='reembolsos_combustivel', null=True,
                                 blank=True)
    diaria = models.ForeignKey('Diaria', on_delete=models.CASCADE, related_name='reembolsos_combustivel', null=True,
                               blank=True, verbose_name="Diária")
    numero_sequencial = models.CharField("Número Sequencial", max_length=50)
    beneficiario = models.ForeignKey('credores.Credor', on_delete=models.PROTECT, limit_choices_to={'tipo': 'PF'},
                                     verbose_name="Beneficiário")

    data_saida = models.DateField("Data de Saída")
    data_retorno = models.DateField("Data de Retorno")
    cidade_origem = models.CharField("Cidade de Origem", max_length=50)
    cidade_destino = models.CharField("Cidade(s) de Destino", max_length=100)

    distancia_km = models.DecimalField("Distância Percorrida (KM)", max_digits=6, decimal_places=2, validators=[MinValueValidator(0.1)])
    preco_combustivel = models.DecimalField("Preço Médio do Combustível (R$)", max_digits=5, decimal_places=2, validators=[MinValueValidator(0.01)])

    valor_total = models.DecimalField("Valor do Reembolso (R$)", max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    objetivo = models.CharField("Objetivo", max_length=200, blank=True, null=True)
    status = models.ForeignKey('StatusChoicesVerbasIndenizatorias', on_delete=models.PROTECT, blank=True, null=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"Reembolso de Combustível: {self.numero_sequencial} - {self.beneficiario}"


class DocumentoReembolso(DocumentoBase):
    """Documento comprobatório associado a reembolso."""

    reembolso = models.ForeignKey('ReembolsoCombustivel', on_delete=models.CASCADE, related_name='documentos')
    history = HistoricalRecords()


class Jeton(models.Model):
    """Pagamento de jeton para participação em reunião/sessão."""

    processo = models.ForeignKey('fluxo.Processo', on_delete=models.CASCADE, related_name='jetons', null=True, blank=True)
    numero_sequencial = models.CharField("Número Sequencial", max_length=50)
    beneficiario = models.ForeignKey('credores.Credor', on_delete=models.PROTECT, limit_choices_to={'tipo': 'PF'},
                                     verbose_name="Conselheiro(a)")

    reuniao = models.CharField("Reunião/Sessão de Referência", max_length=7)

    valor_total = models.DecimalField("Valor Total (R$)", max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.ForeignKey('StatusChoicesVerbasIndenizatorias', on_delete=models.PROTECT, blank=True, null=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"Jeton {self.reuniao} - {self.beneficiario}"


class DocumentoJeton(DocumentoBase):
    """Documento comprobatório associado a jeton."""

    jeton = models.ForeignKey('Jeton', on_delete=models.CASCADE, related_name='documentos')
    history = HistoricalRecords()


class AuxilioRepresentacao(models.Model):
    """Pagamento de auxílio representação para beneficiário elegível."""

    processo = models.ForeignKey('fluxo.Processo', on_delete=models.CASCADE, related_name='auxilios_representacao', null=True,
                                 blank=True)
    numero_sequencial = models.CharField("Número Sequencial", max_length=50)
    beneficiario = models.ForeignKey('credores.Credor', on_delete=models.PROTECT, limit_choices_to={'tipo': 'PF'},
                                     verbose_name="Beneficiário")

    objetivo = models.CharField("Evento/Motivo da Representação", max_length=200, blank=True, null=True,
                                            help_text="Preencha se for representação em evento específico")

    valor_total = models.DecimalField("Valor Total (R$)", max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.ForeignKey('StatusChoicesVerbasIndenizatorias', on_delete=models.PROTECT, blank=True, null=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"Aux. Representação {self.numero_sequencial} - {self.beneficiario}"


class DocumentoAuxilio(DocumentoBase):
    """Documento comprobatório associado a auxílio de representação."""

    auxilio = models.ForeignKey('AuxilioRepresentacao', on_delete=models.CASCADE, related_name='documentos')
    history = HistoricalRecords()


def _make_verba_delete_signal(model_cls):
    """Cria e registra sinal de exclusão para remover arquivo físico do documento."""
    @receiver(post_delete, sender=model_cls, weak=False)
    def _auto_delete(sender, instance, **kwargs):
        """Remove arquivo do storage quando o registro de documento é excluído."""
        _delete_file(instance.arquivo)
    _auto_delete.__name__ = f'auto_delete_file_{model_cls.__name__.lower()}'
    _auto_delete.__qualname__ = _auto_delete.__name__
    return _auto_delete


def _make_verba_presave_signal(model_cls):
    """Cria e registra sinal pre_save para limpar arquivo antigo substituído."""
    @receiver(pre_save, sender=model_cls, weak=False)
    def _cleanup_old_file(sender, instance, **kwargs):
        """Apaga versão anterior do arquivo quando há substituição no mesmo registro."""
        if not instance.pk:
            return
        try:
            old = sender.objects.get(pk=instance.pk)
        except sender.DoesNotExist:
            return
        if old.arquivo and old.arquivo.name and old.arquivo.name != instance.arquivo.name:
            _delete_file(old.arquivo)
    _cleanup_old_file.__name__ = f'cleanup_old_file_{model_cls.__name__.lower()}'
    _cleanup_old_file.__qualname__ = _cleanup_old_file.__name__
    return _cleanup_old_file


for _doc_model in (DocumentoDiaria, DocumentoReembolso, DocumentoJeton, DocumentoAuxilio):
    _make_verba_delete_signal(_doc_model)
    _make_verba_presave_signal(_doc_model)

