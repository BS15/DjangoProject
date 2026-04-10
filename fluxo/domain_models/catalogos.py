"""Catálogos e tabelas parametrizadoras do fluxo financeiro."""

from django.db import models


class StatusChoicesProcesso(models.Model):
    """Catálogo de status possíveis do processo de pagamento."""

    status_choice = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.status_choice}"


class StatusChoicesPendencias(models.Model):
    """Catálogo de status aplicáveis às pendências."""

    status_choice = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.status_choice}"


class TagChoices(models.Model):
    """Etiquetas administrativas usadas para classificação de processos."""

    tag_choice = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tag_choice}"


class FormasDePagamento(models.Model):
    """Formas de pagamento aceitas no fluxo financeiro."""

    forma_de_pagamento = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.forma_de_pagamento}"


class TiposDePagamento(models.Model):
    """Tipos de pagamento utilizados para agrupar regras de negócio."""

    tipo_de_pagamento = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tipo_de_pagamento}"


class TiposDeDocumento(models.Model):
    """Tipos documentais por contexto de pagamento."""

    tipo_de_pagamento = models.ForeignKey("TiposDePagamento", on_delete=models.PROTECT, blank=True, null=True)
    tipo_de_documento = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_de_documento", "tipo_de_pagamento"],
                name="unique_documento_por_pagamento",
            )
        ]

    def __str__(self):
        if self.tipo_de_pagamento:
            return f"{self.tipo_de_documento} ({self.tipo_de_pagamento})"
        return f"{self.tipo_de_documento} (Geral)"


class TiposDePendencias(models.Model):
    """Tipos de pendências operacionais/documentais do processo."""

    tipo_de_pendencia = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tipo_de_pendencia}"
