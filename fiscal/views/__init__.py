"""Views fiscais: retenções de impostos e EFD-REINF."""

from .impostos import painel_impostos_view, agrupar_retencoes_action, api_processar_retencoes
from .reinf.panels import painel_reinf_view
from .reinf.actions import gerar_lote_reinf_action, transmitir_lote_reinf_action

__all__ = [
	"painel_impostos_view",
	"agrupar_retencoes_action",
	"api_processar_retencoes",
	"painel_reinf_view",
	"gerar_lote_reinf_action",
	"transmitir_lote_reinf_action",
]
