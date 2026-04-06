"""Contratos e utilitarios para padronizacao de auditoria/historico."""

from django.db import models
from simple_history.models import HistoricalRecords


class AuditableModelMixin(models.Model):
    """Mixin abstrato para padronizar trilha historica em novos modelos.

    Esta classe nao altera os modelos existentes automaticamente.
    Ela serve como base para migracao incremental de auditoria sem quebra.
    """

    history = HistoricalRecords(inherit=True)

    class Meta:
        abstract = True


__all__ = ["AuditableModelMixin", "HistoricalRecords"]
