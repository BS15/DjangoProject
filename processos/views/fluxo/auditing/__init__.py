"""Auditoria do fluxo financeiro organizada por responsabilidade.

Mantem a interface publica historica de `processos.views.fluxo.auditing`
com separacao entre endpoints de API e painel de visualizacao.
"""

from ..helpers import _build_history_record, _get_unified_history
from .apis import *
from .panels import *

__all__ = [
    "_build_history_record",
    "_get_unified_history",
    "api_documentos_processo",
    "api_processo_detalhes",
    "auditoria_view",
]