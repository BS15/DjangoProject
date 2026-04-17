"""Tax retention management views."""

from .panels import painel_impostos
from .actions import agrupar_impostos_action, anexar_documentos_retencoes_action
from .apis import api_processar_retencoes

__all__ = [
    "painel_impostos",
    "agrupar_impostos_action",
    "anexar_documentos_retencoes_action",
    "api_processar_retencoes",
]
