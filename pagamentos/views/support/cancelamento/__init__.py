"""Views de cancelamento de processo: spoke (GET) e ação (POST)."""

from .panels import *
from .actions import *

__all__ = [
    "cancelar_processo_spoke_view",
    "cancelar_processo_action",
]
