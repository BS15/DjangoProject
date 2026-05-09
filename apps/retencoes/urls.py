"""URLs do aplicativo de retenções fiscais (Impostos e REINF)."""

from django.urls import path

from apps.retencoes.views.impostos import actions as impostos_actions
from apps.retencoes.views.impostos import panels as impostos_panels
from apps.retencoes.views.reinf import actions as reinf_actions
from apps.retencoes.views.reinf import panels as reinf_panels

app_name = 'retencoes'

urlpatterns = [
    # Panels (GET)
    path('impostos/', impostos_panels.painel_impostos_view, name='impostos_list'),
    path('impostos/revisar-agrupamento/', impostos_panels.revisar_agrupamento_retencoes_view, name='revisar_agrupamento_detail'),
    path('reinf/painel/', reinf_panels.painel_reinf_view, name='reinf_list'),

    # Actions (POST)
    path('impostos/preparar-revisao/action/', impostos_actions.preparar_revisao_agrupamento_action, name='preparar_revisao_agrupamento_action'),
    path('impostos/agrupar/action/', impostos_actions.agrupar_retencoes_action, name='agrupar_retencoes_action'),
    path('impostos/anexar-documentos/action/', impostos_actions.anexar_documentos_retencoes_action, name='anexar_documentos_retencoes_action'),
    path('reinf/gerar-lotes/action/', reinf_actions.gerar_lote_reinf_action, name='gerar_lote_reinf_action'),
    path('reinf/transmitir-lotes/action/', reinf_actions.transmitir_lote_reinf_action, name='transmitir_lote_reinf_action'),
]