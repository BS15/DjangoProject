from django.urls import path

from processos.views.fiscal import fiscal_reinf as fiscal_reinf_views
from processos.views.fiscal import fiscal_retencoes as fiscal_retencoes_views
from processos.views.fluxo.payment.comprovantes import panels as comprovantes_panels
from processos.views.fluxo.payment.comprovantes import actions as comprovantes_actions
from processos.views.fluxo.pre_payment.liquidacoes import panels as liquidacoes_panels
from processos.views.fluxo.pre_payment.liquidacoes import actions as liquidacoes_actions
from processos.views.fluxo.pre_payment.cadastro import documentos as documentos_fiscais_views

urlpatterns = [
    path('retencao-impostos/', fiscal_retencoes_views.painel_impostos, name='painel_impostos'),
    path('impostos/agrupar/', fiscal_retencoes_views.agrupar_impostos_view, name='agrupar_impostos'),
    path('processos/comprovantes/', comprovantes_panels.painel_comprovantes_view, name='painel_comprovantes'),
    path('api/comprovantes/fatiar/', comprovantes_actions.api_fatiar_comprovantes, name='api_fatiar_comprovantes'),
    path('api/comprovantes/vincular/', comprovantes_actions.api_vincular_comprovantes, name='api_vincular_comprovantes'),
    path('liquidacoes/', liquidacoes_panels.painel_liquidacoes_view, name='painel_liquidacoes'),
    path('liquidacoes/atestar/<int:pk>/', liquidacoes_actions.alternar_ateste_nota, name='alternar_ateste_nota'),
    path('processo/<int:pk>/documentos-fiscais/', documentos_fiscais_views.documentos_fiscais_view, name='documentos_fiscais'),
    path('api/processo/<int:processo_pk>/toggle-documento-fiscal/<int:documento_pk>/', documentos_fiscais_views.api_toggle_documento_fiscal, name='api_toggle_documento_fiscal'),
    path('api/processo/<int:processo_pk>/salvar-nota-fiscal/<int:nota_pk>/', documentos_fiscais_views.api_salvar_nota_fiscal, name='api_salvar_nota_fiscal'),
    path('api/processar-retencoes/', fiscal_retencoes_views.api_processar_retencoes, name='api_processar_retencoes'),
    path('reinf/painel/', fiscal_reinf_views.painel_reinf_view, name='painel_reinf'),
    path('reinf/gerar-lotes/', fiscal_reinf_views.gerar_lote_reinf_view, name='gerar_lote_reinf'),
]
