"""Endpoints da etapa de conselho fiscal do pos-pagamento."""

from .actions import *
from .panels import *
from .reviews import *

__all__ = [
    "painel_conselho_view",
    "conselho_processo_view",
    "aprovar_conselho_view",
    "recusar_conselho_view",
    "gerar_parecer_conselho_view",
]
