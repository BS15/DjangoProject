"""Views da contingencia: paineis (GET) e acoes (POST)."""

from .panels import *
from .actions import *

__all__ = [
    "painel_contingencias_view",
    "add_contingencia_view",
    "add_contingencia_action",
    "analisar_contingencia_action",
]
