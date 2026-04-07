"""Facade de compatibilidade para telas de revisao de pos-pagamento."""

from .conferencia.reviews import *
from .contabilizacao.reviews import *
from .conselho.reviews import *
from .arquivamento.reviews import *


__all__ = [
    "conferencia_processo_view",
    "contabilizacao_processo_view",
    "conselho_processo_view",
    "gerar_parecer_conselho_view",
    "arquivar_processo_view",
]