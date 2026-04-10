"""Endpoints da etapa de arquivamento do pos-pagamento."""

from .actions import *
from .panels import *
from .reviews import *

__all__ = [
    "painel_arquivamento_view",
    "arquivar_processo_view",
    "arquivar_processo_action",
]
