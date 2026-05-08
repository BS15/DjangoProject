"""Views de contingencia: paineis (GET) e acoes (POST)."""

from .panels import *
from .actions import *

__all__ = [
    "painel_contingencias_diarias_view",
    "add_contingencia_diaria_view",
    "add_contingencia_diaria_action",
    "analisar_contingencia_diaria_action",
]
