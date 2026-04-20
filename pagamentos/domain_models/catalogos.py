"""Catálogos e tabelas parametrizadoras do fluxo financeiro.

Este módulo define modelos de catálogos e tabelas de apoio do domínio de fluxo financeiro.
Inclui tabelas de status, tipos de pagamento, documentos e pendências utilizadas nos processos financeiros e documentais.
"""

from django.db import models



# Renomeações para padronização em português brasileiro
class StatusOpcoesProcesso(models.Model):
    """Catálogo de status possíveis do processo de pagamento."""
    opcao_status = models.CharField(max_length=100, unique=True)
    ativo = models.BooleanField(default=True)
    def __str__(self):
        return f"{self.opcao_status}"

class StatusOpcoesPendencia(models.Model):
    """Catálogo de status aplicáveis às pendências."""
    opcao_status = models.CharField(max_length=100, unique=True)
    ativo = models.BooleanField(default=True)
    def __str__(self):
        return f"{self.opcao_status}"

class OpcoesEtiqueta(models.Model):
    """Etiquetas administrativas usadas para classificação de processos."""
    opcao_etiqueta = models.CharField(max_length=100, unique=True)
    ativo = models.BooleanField(default=True)
    def __str__(self):
        return f"{self.opcao_etiqueta}"

class FormasPagamento(models.Model):
    """Formas de pagamento aceitas no fluxo financeiro."""
    forma_pagamento = models.CharField(max_length=100, unique=True)
    ativo = models.BooleanField(default=True)
    def __str__(self):
        return f"{self.forma_pagamento}"

class TiposPagamento(models.Model):
    """Tipos de pagamento utilizados para agrupar regras de negócio."""
    tipo_pagamento = models.CharField(max_length=100, unique=True)
    ativo = models.BooleanField(default=True)
    def __str__(self):
        return f"{self.tipo_pagamento}"

class TiposDocumento(models.Model):
    """Tipos documentais por contexto de pagamento."""
    tipo_pagamento = models.ForeignKey("TiposPagamento", on_delete=models.PROTECT, blank=True, null=True)
    tipo_documento = models.CharField(max_length=100)
    ativo = models.BooleanField(default=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_documento", "tipo_pagamento"],
                name="unique_documento_por_pagamento",
            )
        ]
    def __str__(self):
        if self.tipo_pagamento:
            return f"{self.tipo_documento} ({self.tipo_pagamento})"
        return f"{self.tipo_documento} (Geral)"

class TiposPendencia(models.Model):
    """Tipos de pendências operacionais/documentais do processo."""
    tipo_pendencia = models.CharField(max_length=100, unique=True)
    ativo = models.BooleanField(default=True)
    def __str__(self):
        return f"{self.tipo_pendencia}"
