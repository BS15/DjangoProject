"""Views de devolucao: paineis (GET) e acoes (POST)."""

from .panels import *
from .actions import *

__all__ = [
    "painel_devolucoes_view",
    "registrar_devolucao_view",
    "registrar_devolucao_action",
]
