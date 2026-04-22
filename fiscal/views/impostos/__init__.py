"""Tax retention management views."""

from .panels import painel_impostos_view, revisar_agrupamento_retencoes_view
from .actions import (
    preparar_revisao_agrupamento_action,
    agrupar_retencoes_action,
    anexar_documentos_retencoes_action,
)
from .apis import api_processar_retencoes

__all__ = [
    "painel_impostos_view",
    "revisar_agrupamento_retencoes_view",
    "preparar_revisao_agrupamento_action",
    "agrupar_retencoes_action",
    "anexar_documentos_retencoes_action",
    "api_processar_retencoes",
]
