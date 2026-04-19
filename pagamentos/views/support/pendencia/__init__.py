"""Views de pendencias: paineis (GET) e acoes (POST)."""

from .panels import *
from .actions import *

__all__ = [
    "painel_pendencias_view",
    "atualizar_pendencias_lote_action",
]
