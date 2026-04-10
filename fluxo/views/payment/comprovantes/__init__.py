"""Endpoints da etapa de comprovantes de pagamento."""

from .actions import *
from .panels import *

__all__ = [
    "painel_comprovantes_view",
    "api_fatiar_comprovantes",
    "api_vincular_comprovantes",
]
