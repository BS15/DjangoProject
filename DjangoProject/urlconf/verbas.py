from django.urls import path

from verbas_indenizatorias.views.processo import actions as verbas_actions
from verbas_indenizatorias.views.processo import api as verbas_api
from verbas_indenizatorias.views.processo import forms as verbas_forms
from verbas_indenizatorias.views.processo import panels as verbas_panels
from verbas_indenizatorias.views.auxilios import forms as verbas_auxilio_forms
from verbas_indenizatorias.views.auxilios import panels as verbas_auxilio_panels
from verbas_indenizatorias.views.diarias import actions as verbas_diarias_actions
from verbas_indenizatorias.views.diarias import api as verbas_diarias_api
from verbas_indenizatorias.views.diarias import forms as verbas_diarias_forms
from verbas_indenizatorias.views.diarias import imports as verbas_diarias_imports
from verbas_indenizatorias.views.diarias import panels as verbas_diarias_panels
from verbas_indenizatorias.views.diarias import pdf as verbas_diarias_pdf
from verbas_indenizatorias.views.diarias import signatures as verbas_diarias_signatures
from verbas_indenizatorias.views.diarias import sync as verbas_diarias_sync
from verbas_indenizatorias.views.jetons import forms as verbas_jeton_forms
from verbas_indenizatorias.views.jetons import panels as verbas_jeton_panels
from verbas_indenizatorias.views.reembolsos import forms as verbas_reembolso_forms
from verbas_indenizatorias.views.reembolsos import panels as verbas_reembolso_panels

urlpatterns = [
    path('processo/<int:pk>/editar-verbas/', verbas_forms.editar_processo_verbas, name='editar_processo_verbas'),
    path('api/verba/<str:tipo_verba>/<int:pk>/add-documento/', verbas_api.api_add_documento_verba, name='api_add_documento_verba'),
    path('verbas/', verbas_panels.verbas_panel_view, name='verbas_panel'),
    path('verbas/diarias/', verbas_diarias_panels.diarias_list_view, name='diarias_list'),
    path('verbas/reembolsos/', verbas_reembolso_panels.reembolsos_list_view, name='reembolsos_list'),
    path('verbas/jetons/', verbas_jeton_panels.jetons_list_view, name='jetons_list'),
    path('verbas/auxilios/', verbas_auxilio_panels.auxilios_list_view, name='auxilios_list'),
    path('verbas/diarias/nova/', verbas_diarias_forms.add_diaria_view, name='add_diaria'),
    path('verbas/diarias/<int:pk>/gerenciar/', verbas_diarias_forms.gerenciar_diaria_view, name='gerenciar_diaria'),
    path('verbas/reembolsos/novo/', verbas_reembolso_forms.add_reembolso_view, name='add_reembolso'),
    path('verbas/jetons/novo/', verbas_jeton_forms.add_jeton_view, name='add_jeton'),
    path('verbas/auxilios/novo/', verbas_auxilio_forms.add_auxilio_view, name='add_auxilio'),
    path('verbas/reembolsos/<int:pk>/editar/', verbas_reembolso_forms.edit_reembolso_view, name='edit_reembolso'),
    path('verbas/jetons/<int:pk>/editar/', verbas_jeton_forms.edit_jeton_view, name='edit_jeton'),
    path('verbas/auxilios/<int:pk>/editar/', verbas_auxilio_forms.edit_auxilio_view, name='edit_auxilio'),
    path('verbas/agrupar/<str:tipo_verba>/', verbas_actions.agrupar_verbas_view, name='agrupar_verbas'),
    path('api/valor-unitario-diaria/<int:beneficiario_id>/', verbas_diarias_api.api_valor_unitario_diaria, name='api_valor_unitario_diaria'),
    path('verbas/diarias/autorizacao/', verbas_diarias_actions.painel_autorizacao_diarias_view, name='painel_autorizacao_diarias'),
    path('verbas/diarias/autorizacao/<int:pk>/alternar/', verbas_diarias_actions.alternar_autorizacao_diaria, name='alternar_autorizacao_diaria'),
    path('verbas/diarias/<int:diaria_id>/aprovar/', verbas_diarias_actions.aprovar_diaria_view, name='aprovar_diaria'),
    path('verbas/diarias/<int:pk>/pcd/', verbas_diarias_pdf.gerar_pcd_view, name='gerar_pcd'),
    path('verbas/sincronizar-diarias/', verbas_diarias_sync.sincronizar_diarias, name='sincronizar_diarias'),
    path('verbas/diarias/importar/', verbas_diarias_imports.importar_diarias_view, name='importar_diarias'),
    path('verbas/diarias/template-csv/', verbas_diarias_panels.download_template_diarias_csv, name='download_template_diarias_csv'),
    path('verbas/diarias/<int:assinatura_id>/sincronizar/', verbas_diarias_signatures.sincronizar_assinatura_view, name='sincronizar_assinatura'),
    path('verbas/diarias/<int:diaria_id>/reenviar-assinatura/', verbas_diarias_signatures.reenviar_assinatura_view, name='reenviar_assinatura'),
    path('verbas/minhas-solicitacoes/', verbas_diarias_panels.minhas_solicitacoes_view, name='minhas_solicitacoes'),
]
