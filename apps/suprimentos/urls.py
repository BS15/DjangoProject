"""URLs do aplicativo de Suprimentos."""

from django.urls import path

from apps.suprimentos.views.cadastro import actions as suprimento_cadastro_actions
from apps.suprimentos.views.cadastro import panels as suprimento_cadastro_panels
from apps.suprimentos.views.prestacao_contas import actions as suprimento_actions
from apps.suprimentos.views.prestacao_contas import panels as suprimento_panels
from apps.suprimentos.views.prestacao_contas import pdf as suprimento_pdf

app_name = 'suprimentos'

urlpatterns = [
    # Panels (GET)
    path('', suprimento_panels.painel_suprimentos_view, name='suprimentos_list'),
    path('novo/', suprimento_cadastro_panels.add_suprimento_view, name='suprimento_create'),
    path('<int:pk>/gerenciar/', suprimento_panels.gerenciar_suprimento_view, name='suprimento_detail'),
    path('<int:pk>/cancelar/', suprimento_panels.cancelar_suprimento_spoke_view, name='cancelar_suprimento_spoke'),
    path('<int:pk>/despesas/nova/', suprimento_panels.adicionar_despesa_view, name='adicionar_despesa_create'),
    path('prestacoes/revisar/', suprimento_panels.revisar_prestacoes_suprimento_view, name='revisar_prestacoes_list'),
    path('prestacoes/<int:pk>/revisar/', suprimento_panels.revisar_prestacao_suprimento_view, name='revisar_prestacao_detail'),
    path('<int:pk>/prestacao/relatorio/', suprimento_pdf.gerar_relatorio_prestacao_contas_view, name='relatorio_prestacao_contas_pdf'),

    # Actions (POST)
    path('novo/action/', suprimento_cadastro_actions.add_suprimento_action, name='add_suprimento_action'),
    path('<int:pk>/despesas/adicionar/action/', suprimento_actions.adicionar_despesa_action, name='adicionar_despesa_action'),
    path('<int:pk>/fechar/action/', suprimento_actions.fechar_suprimento_action, name='fechar_suprimento_action'),
    path('<int:pk>/prestacao/enviar/action/', suprimento_actions.enviar_prestacao_suprimento_action, name='enviar_prestacao_suprimento_action'),
    path('prestacoes/<int:pk>/aprovar/action/', suprimento_actions.aprovar_prestacao_suprimento_action, name='aprovar_prestacao_suprimento_action'),
    path('<int:pk>/cancelar/action/', suprimento_actions.cancelar_suprimento_action, name='cancelar_suprimento_action'),
]