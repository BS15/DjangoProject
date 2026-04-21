"""Tax retention management views."""

from .panels import painel_impostos_view
from .actions import (
    agrupar_retencoes_action,
    anexar_documentos_retencoes_action,
)
from .apis import api_processar_retencoes

__all__ = [
    "painel_impostos_view",
    "agrupar_retencoes_action",
    "anexar_documentos_retencoes_action",
    "api_processar_retencoes",
]
