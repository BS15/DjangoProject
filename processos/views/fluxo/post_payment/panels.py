"""Facade de compatibilidade para paineis de pos-pagamento."""

from .conferencia.panels import *
from .contabilizacao.panels import *
from .conselho.panels import *
from .reunioes.panels import *
from .arquivamento.panels import *


__all__ = [
    "painel_conferencia_view",
    "painel_contabilizacao_view",
    "painel_conselho_view",
    "gerenciar_reunioes_view",
    "montar_pauta_reuniao_view",
    "analise_reuniao_view",
    "painel_arquivamento_view",
]