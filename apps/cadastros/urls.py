"""URLs do aplicativo de cadastros."""

from django.urls import path

from apps.cadastros import actions as credor_actions
from apps.cadastros import panels as credor_panels
from apps.cadastros import imports as credores_import_views

app_name = 'cadastros'

urlpatterns = [
    path('credores/', credor_panels.credores_list_view, name='credores_list'),
    path('credores/novo/', credor_panels.add_credor_view, name='credor_create'),
    path('credores/novo/action/', credor_actions.add_credor_action, name='add_credor_action'),
    path('credores/<int:pk>/gerenciar/', credor_panels.gerenciar_credor_view, name='credor_detail'),
    path('credores/<int:pk>/editar/', credor_panels.gerenciar_credor_view, name='credor_edit'),
    path('credores/<int:pk>/editar/action/', credor_actions.edit_credor_action, name='edit_credor_action'),
    path('credores/<int:pk>/toggle-status/action/', credor_actions.toggle_status_credor_action, name='toggle_status_credor_action'),
    path('api/credor/<int:credor_id>/', credor_panels.api_dados_credor, name='api_dados_credor'),
    path('importar-siscac/', credores_import_views.painel_importacao_view, name='importacao_siscac_detail'),
    path('importar-siscac/template-credores/', credores_import_views.download_template_csv_credores, name='template_csv_credores'),
]