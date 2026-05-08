"""Views de sincronizacao de diarias: paineis (GET) e acoes (POST)."""

from .panels import *
from .actions import *

__all__ = [
    "sincronizar_diarias_view",
    "sincronizar_diarias_action",
]
