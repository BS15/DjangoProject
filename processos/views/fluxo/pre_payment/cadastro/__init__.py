"""Endpoints da etapa de cadastro, edição e documentos fiscais no pré-pagamento."""

from .documentos import *
from .forms import *

__all__ = [
    "add_process_view",
    "editar_processo",
    "editar_processo_capa_view",
    "editar_processo_documentos_view",
    "editar_processo_pendencias_view",
    "documentos_fiscais_view",
    "api_toggle_documento_fiscal",
    "api_salvar_nota_fiscal",
]

