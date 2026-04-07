"""Facade de compatibilidade para formularios de pre-pagamento."""

from .cadastro.forms import *


__all__ = [
    "add_process_view",
    "editar_processo",
    "editar_processo_capa_view",
    "editar_processo_documentos_view",
    "editar_processo_pendencias_view",
]
