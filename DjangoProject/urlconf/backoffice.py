from django.urls import path

from processos.views import cadastros as cadastro_views
from processos.views import suprimentos as suprimento_views
from processos.views.sistemas_auxiliares import assinaturas as assinatura_views
from processos.views.sistemas_auxiliares import contas as conta_views
from processos.views.sistemas_auxiliares import relatorios as relatorio_views
from processos.views.sistemas_auxiliares.imports import credores as credores_import_views

urlpatterns = [
    path('adicionar-credor/', cadastro_views.add_credor_view, name='add_credor'),
    path('credores/', cadastro_views.credores_list_view, name='credores_list'),
    path('credores/<int:pk>/editar/', cadastro_views.edit_credor_view, name='edit_credor'),
    path('api/credor/<int:credor_id>/', cadastro_views.api_dados_credor, name='api_dados_credor'),
    path('suprimentos/', suprimento_views.painel_suprimentos_view, name='painel_suprimentos'),
    path('suprimentos/<int:pk>/gerenciar/', suprimento_views.gerenciar_suprimento_view, name='gerenciar_suprimento'),
    path('suprimentos/<int:pk>/despesas/adicionar/', suprimento_views.adicionar_despesa_action, name='adicionar_despesa_action'),
    path('suprimentos/<int:pk>/fechar/', suprimento_views.fechar_suprimento_action, name='fechar_suprimento_action'),
    path('suprimentos/novo/', suprimento_views.add_suprimento_view, name='add_suprimento'),
    path('importar-siscac/', credores_import_views.painel_importacao_view, name='painel_importacao'),
    path('importar-siscac/template-credores/', credores_import_views.download_template_csv_credores, name='template_csv_credores'),
    path('importar-siscac/template-contas/', credores_import_views.download_template_csv_contas, name='template_csv_contas'),
    path('contas-fixas/', conta_views.painel_contas_fixas_view, name='painel_contas_fixas'),
    path('contas-fixas/nova/', conta_views.add_conta_fixa_view, name='add_conta_fixa'),
    path('contas-fixas/<int:pk>/editar/', conta_views.edit_conta_fixa_view, name='edit_conta_fixa'),
    path('contas-fixas/<int:pk>/excluir/', conta_views.excluir_conta_fixa_view, name='excluir_conta_fixa'),
    path('contas-fixas/<int:fatura_id>/vincular/', conta_views.vincular_processo_fatura_view, name='vincular_processo_fatura'),
    path('relatorios/', relatorio_views.painel_relatorios_view, name='painel_relatorios'),
    path('relatorios/documentos-gerados/', relatorio_views.relatorio_documentos_gerados_view, name='relatorio_documentos_gerados'),
    path('assinaturas/', assinatura_views.painel_assinaturas_view, name='painel_assinaturas'),
    path('assinaturas/disparar/<int:assinatura_id>/', assinatura_views.disparar_assinatura_view, name='disparar_assinatura'),
]
