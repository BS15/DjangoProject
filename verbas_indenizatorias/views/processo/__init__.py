"""Endpoints transversais de processos de verbas indenizatorias."""

from .actions import *
from .apis import *
from .forms import *
from .panels import *

__all__ = [
    "verbas_panel_view",
    "agrupar_verbas_view",
    "painel_revisar_solicitacoes_view",
    "revisar_solicitacao_verba_view",
    "aprovar_revisao_solicitacao_action",
    "editar_processo_verbas_view",
    "editar_processo_verbas_capa_view",
    "editar_processo_verbas_pendencias_view",
    "editar_processo_verbas_itens_view",
    "editar_processo_verbas_documentos_view",
    "editar_processo_verbas_capa_action",
    "editar_processo_verbas_pendencias_action",
    "editar_processo_verbas_documentos_action",
    "api_add_documento_verba",
]
