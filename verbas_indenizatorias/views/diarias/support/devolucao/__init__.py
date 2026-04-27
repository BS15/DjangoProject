"""Views de devolucao: paineis (GET) e acoes (POST)."""

from .panels import *
from .actions import *

__all__ = [
    "painel_devolucoes_diarias_view",
    "registrar_devolucao_diaria_view",
    "registrar_devolucao_diaria_action",
]
