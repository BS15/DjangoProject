"""Tax retention management views."""

from .panels import painel_impostos
from .actions import agrupar_impostos_view
from .apis import api_processar_retencoes

__all__ = [
    "painel_impostos",
    "agrupar_impostos_view",
    "api_processar_retencoes",
]
