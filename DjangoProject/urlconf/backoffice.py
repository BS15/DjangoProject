from django.urls import path

from credores import imports as credores_import_views
from fluxo.views.support import reports as relatorio_views
from fluxo.views.support import signatures as assinatura_views
from fluxo.views.support.contas_fixas import imports as conta_fixa_imports
from fluxo.views.support.contas_fixas import actions as conta_actions
from fluxo.views.support.contas_fixas import panels as conta_panels
from credores import actions as credor_actions
from credores import panels as credor_panels
from suprimentos.views.cadastro import actions as suprimento_cadastro_actions
from suprimentos.views.cadastro import panels as suprimento_cadastro_panels
from suprimentos.views.prestacao_contas import actions as suprimento_actions
from suprimentos.views.prestacao_contas import panels as suprimento_panels

urlpatterns = [
    path('adicionar-credor/', credor_panels.add_credor_view, name='add_credor_view'),
    path('adicionar-credor/', credor_panels.add_credor_view, name='add_credor'),
    path('adicionar-credor/action/', credor_actions.add_credor_action, name='add_credor_action'),
    path('credores/', credor_panels.credores_list_view, name='credores_list'),
    path('credores/<int:pk>/gerenciar/', credor_panels.gerenciar_credor_view, name='gerenciar_credor_view'),
    path('credores/<int:pk>/editar/', credor_panels.gerenciar_credor_view, name='edit_credor'),
    path('credores/<int:pk>/editar/action/', credor_actions.edit_credor_action, name='edit_credor_action'),
    path('credores/<int:pk>/toggle-status/', credor_actions.toggle_status_credor_action, name='toggle_status_credor_action'),
    path('api/credor/<int:credor_id>/', credor_panels.api_dados_credor, name='api_dados_credor'),
    path('suprimentos/', suprimento_panels.painel_suprimentos_view, name='suprimentos_list'),
    path('suprimentos/<int:pk>/gerenciar/', suprimento_panels.gerenciar_suprimento_view, name='gerenciar_suprimento_view'),
    path('suprimentos/<int:pk>/despesas/nova/', suprimento_panels.adicionar_despesa_view, name='adicionar_despesa_view'),
    path('suprimentos/<int:pk>/despesas/adicionar/', suprimento_actions.adicionar_despesa_action, name='registrar_despesa_action'),
    path('suprimentos/<int:pk>/fechar/', suprimento_actions.fechar_suprimento_action, name='concluir_prestacao_action'),
    path('suprimentos/novo/', suprimento_cadastro_panels.add_suprimento_view, name='add_suprimento_view'),
    path('suprimentos/novo/action/', suprimento_cadastro_actions.add_suprimento_action, name='add_suprimento_action'),
    path('importar-siscac/', credores_import_views.painel_importacao_view, name='painel_importacao'),
    path('importar-siscac/template-credores/', credores_import_views.download_template_csv_credores, name='template_csv_credores'),
    path('importar-siscac/template-contas/', conta_fixa_imports.download_template_csv_contas, name='template_csv_contas'),
    path('contas-fixas/', conta_panels.painel_contas_fixas_view, name='painel_contas_fixas'),
    path('contas-fixas/nova/', conta_panels.add_conta_fixa_view, name='add_conta_fixa'),
    path('contas-fixas/nova/action/', conta_actions.add_conta_fixa_action, name='add_conta_fixa_action'),
    path('contas-fixas/<int:pk>/editar/', conta_panels.edit_conta_fixa_view, name='edit_conta_fixa'),
    path('contas-fixas/<int:pk>/editar/action/', conta_actions.edit_conta_fixa_action, name='edit_conta_fixa_action'),
    path('contas-fixas/<int:pk>/excluir/', conta_actions.excluir_conta_fixa_action, name='excluir_conta_fixa'),
    path('contas-fixas/<int:fatura_id>/vincular/', conta_actions.vincular_processo_fatura_action, name='vincular_processo_fatura'),
    path('relatorios/', relatorio_views.painel_relatorios_view, name='painel_relatorios'),
    path('relatorios/documentos-gerados/', relatorio_views.relatorio_documentos_gerados_view, name='relatorio_documentos_gerados'),
    path('assinaturas/', assinatura_views.painel_assinaturas_view, name='painel_assinaturas'),
    path('assinaturas/disparar/<int:assinatura_id>/', assinatura_views.disparar_assinatura_view, name='disparar_assinatura'),
]
