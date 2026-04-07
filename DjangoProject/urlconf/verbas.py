from django.urls import path

from processos.views import verbas as verbas_views
from processos.views.verbas import siscac_diarias_sync as verbas_sync_views
from processos.views.verbas import verbas_auxilio as verbas_auxilio_views
from processos.views.verbas import verbas_diarias as verbas_diarias_views
from processos.views.verbas import verbas_jeton as verbas_jeton_views
from processos.views.verbas import verbas_reembolso as verbas_reembolso_views

urlpatterns = [
    path('processo/<int:pk>/editar-verbas/', verbas_views.editar_processo_verbas, name='editar_processo_verbas'),
    path('api/verba/<str:tipo_verba>/<int:pk>/add-documento/', verbas_views.api_add_documento_verba, name='api_add_documento_verba'),
    path('verbas/', verbas_views.verbas_panel_view, name='verbas_panel'),
    path('verbas/diarias/', verbas_diarias_views.diarias_list_view, name='diarias_list'),
    path('verbas/reembolsos/', verbas_reembolso_views.reembolsos_list_view, name='reembolsos_list'),
    path('verbas/jetons/', verbas_jeton_views.jetons_list_view, name='jetons_list'),
    path('verbas/auxilios/', verbas_auxilio_views.auxilios_list_view, name='auxilios_list'),
    path('verbas/diarias/nova/', verbas_diarias_views.add_diaria_view, name='add_diaria'),
    path('verbas/diarias/<int:pk>/gerenciar/', verbas_diarias_views.gerenciar_diaria_view, name='gerenciar_diaria'),
    path('verbas/reembolsos/novo/', verbas_reembolso_views.add_reembolso_view, name='add_reembolso'),
    path('verbas/jetons/novo/', verbas_jeton_views.add_jeton_view, name='add_jeton'),
    path('verbas/auxilios/novo/', verbas_auxilio_views.add_auxilio_view, name='add_auxilio'),
    path('verbas/reembolsos/<int:pk>/editar/', verbas_reembolso_views.edit_reembolso_view, name='edit_reembolso'),
    path('verbas/jetons/<int:pk>/editar/', verbas_jeton_views.edit_jeton_view, name='edit_jeton'),
    path('verbas/auxilios/<int:pk>/editar/', verbas_auxilio_views.edit_auxilio_view, name='edit_auxilio'),
    path('verbas/agrupar/<str:tipo_verba>/', verbas_views.agrupar_verbas_view, name='agrupar_verbas'),
    path('api/valor-unitario-diaria/<int:beneficiario_id>/', verbas_diarias_views.api_valor_unitario_diaria, name='api_valor_unitario_diaria'),
    path('verbas/diarias/autorizacao/', verbas_diarias_views.painel_autorizacao_diarias_view, name='painel_autorizacao_diarias'),
    path('verbas/diarias/autorizacao/<int:pk>/alternar/', verbas_diarias_views.alternar_autorizacao_diaria, name='alternar_autorizacao_diaria'),
    path('verbas/diarias/<int:diaria_id>/aprovar/', verbas_diarias_views.aprovar_diaria_view, name='aprovar_diaria'),
    path('verbas/diarias/<int:pk>/pcd/', verbas_diarias_views.gerar_pcd_view, name='gerar_pcd'),
    path('verbas/sincronizar-diarias/', verbas_sync_views.sincronizar_diarias, name='sincronizar_diarias'),
    path('verbas/diarias/importar/', verbas_diarias_views.importar_diarias_view, name='importar_diarias'),
    path('verbas/diarias/template-csv/', verbas_diarias_views.download_template_diarias_csv, name='download_template_diarias_csv'),
    path('verbas/diarias/<int:assinatura_id>/sincronizar/', verbas_diarias_views.sincronizar_assinatura_view, name='sincronizar_assinatura'),
    path('verbas/diarias/<int:diaria_id>/reenviar-assinatura/', verbas_diarias_views.reenviar_assinatura_view, name='reenviar_assinatura'),
    path('verbas/minhas-solicitacoes/', verbas_diarias_views.minhas_solicitacoes_view, name='minhas_solicitacoes'),
]
