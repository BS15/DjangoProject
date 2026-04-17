from django.urls import path

from fiscal.views.impostos import apis as impostos_apis
from fiscal.views.impostos import panels as impostos_panels
from fiscal.views.impostos import actions as impostos_actions
from fiscal.views.reinf import actions as reinf_actions
from fiscal.views.reinf import panels as reinf_panels
from fluxo.views.payment.comprovantes import panels as comprovantes_panels
from fluxo.views.payment.comprovantes import apis as comprovantes_apis
from fluxo.views.pre_payment.liquidacoes import panels as liquidacoes_panels
from fluxo.views.pre_payment.liquidacoes import actions as liquidacoes_actions
from fluxo.views.pre_payment.cadastro import panels as documentos_fiscais_panels
from fluxo.views.pre_payment.cadastro import apis as documentos_fiscais_apis

urlpatterns = [
    path('retencao-impostos/', impostos_panels.painel_impostos_view, name='painel_impostos_view'),
    path('retencao-impostos/legacy/', impostos_panels.painel_impostos, name='painel_impostos'),
    path('impostos/agrupar/', impostos_actions.agrupar_retencoes_action, name='agrupar_retencoes_action'),
    path('impostos/agrupar/legacy/', impostos_actions.agrupar_impostos_action, name='agrupar_impostos'),
    path('impostos/anexar-documentos/', impostos_actions.anexar_documentos_retencoes_action, name='anexar_documentos_retencoes_action'),
    path('processos/comprovantes/', comprovantes_panels.painel_comprovantes_view, name='painel_comprovantes'),
    path('api/comprovantes/fatiar/', comprovantes_apis.api_fatiar_comprovantes, name='api_fatiar_comprovantes'),
    path('api/comprovantes/vincular/', comprovantes_apis.api_vincular_comprovantes, name='api_vincular_comprovantes'),
    path('liquidacoes/', liquidacoes_panels.painel_liquidacoes_view, name='painel_liquidacoes'),
    path('liquidacoes/atestar/<int:pk>/', liquidacoes_actions.alternar_ateste_nota_action, name='alternar_ateste_nota'),
    path('processo/<int:pk>/documentos-fiscais/', documentos_fiscais_panels.documentos_fiscais_view, name='documentos_fiscais'),
    path('api/processo/<int:processo_pk>/toggle-documento-fiscal/<int:documento_pk>/', documentos_fiscais_apis.api_toggle_documento_fiscal, name='api_toggle_documento_fiscal'),
    path('api/processo/<int:processo_pk>/salvar-nota-fiscal/<int:nota_pk>/', documentos_fiscais_apis.api_salvar_nota_fiscal, name='api_salvar_nota_fiscal'),
    path('api/processar-retencoes/', impostos_apis.api_processar_retencoes, name='api_processar_retencoes'),
    path('reinf/painel/', reinf_panels.painel_reinf_view, name='painel_reinf_view'),
    path('reinf/painel/legacy/', reinf_panels.painel_reinf_view, name='painel_reinf'),
    path('reinf/gerar-lotes/', reinf_actions.gerar_lote_reinf_action, name='gerar_lote_reinf_action'),
    path('reinf/transmitir-lotes/', reinf_actions.transmitir_lote_reinf_action, name='transmitir_lote_reinf_action'),
    path('reinf/gerar-lotes/legacy/', reinf_actions.gerar_lote_reinf_legacy_action, name='gerar_lote_reinf'),
]
