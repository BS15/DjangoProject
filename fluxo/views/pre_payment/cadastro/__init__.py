"""Endpoints da etapa de documentos fiscais do cadastro."""

from .actions import *  # noqa: F401, F403
from .panels import *  # noqa: F401, F403

__all__ = [
    "documentos_fiscais_view",
    "api_toggle_documento_fiscal",
    "api_salvar_nota_fiscal",
]

