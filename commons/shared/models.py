
"""Modelos abstratos compartilhados entre múltiplos apps de domínio.

Este módulo define modelos base reutilizáveis para documentos e entidades comuns a múltiplos domínios do sistema.
"""

from django.db import models

from commons.shared.file_validators import validar_arquivo_seguro
from commons.shared.storage_utils import caminho_documento


class DocumentoBase(models.Model):
    """Classe abstrata base para documentos anexados com ordenação."""

    arquivo = models.FileField(upload_to=caminho_documento, validators=[validar_arquivo_seguro])
    ordem = models.PositiveIntegerField(default=1, help_text="Ordem do arquivo")
    tipo = models.ForeignKey("fluxo.TiposDeDocumento", on_delete=models.PROTECT)

    class Meta:
        abstract = True
        ordering = ["ordem"]


__all__ = ["DocumentoBase"]
