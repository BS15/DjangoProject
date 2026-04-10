"""Endpoints transversais de processos de verbas indenizatorias."""

from .actions import *
from .api import *
from .forms import *
from .panels import *

__all__ = [
    "verbas_panel_view",
    "agrupar_verbas_view",
    "editar_processo_verbas",
    "api_add_documento_verba",
]
