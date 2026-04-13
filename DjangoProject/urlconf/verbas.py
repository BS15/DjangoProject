from django.urls import path

from verbas_indenizatorias.views.processo import actions as verbas_actions
from verbas_indenizatorias.views.processo import api as verbas_api
from verbas_indenizatorias.views.processo import forms as verbas_forms
from verbas_indenizatorias.views.processo import panels as verbas_panels
from verbas_indenizatorias.views.auxilios import actions as verbas_auxilio_actions
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
from verbas_indenizatorias.views.jetons import actions as verbas_jeton_actions
from verbas_indenizatorias.views.jetons import forms as verbas_jeton_forms
from verbas_indenizatorias.views.jetons import panels as verbas_jeton_panels
from verbas_indenizatorias.views.reembolsos import actions as verbas_reembolso_actions
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
    path('verbas/diarias/nova/', verbas_diarias_panels.add_diaria_view, name='add_diaria'),
    path('verbas/diarias/nova/action/', verbas_diarias_actions.add_diaria_action, name='add_diaria_action'),
    path('verbas/diarias/<int:pk>/gerenciar/', verbas_diarias_panels.gerenciar_diaria_view, name='gerenciar_diaria'),
    path('verbas/diarias/<int:pk>/solicitar-autorizacao/', verbas_diarias_actions.solicitar_autorizacao_action, name='solicitar_autorizacao_action'),
    path('verbas/diarias/<int:pk>/autorizar/', verbas_diarias_actions.autorizar_diaria_action, name='autorizar_diaria_action'),
    path('verbas/diarias/<int:pk>/comprovantes/registrar/', verbas_diarias_actions.registrar_comprovante_action, name='registrar_comprovante_action'),
    path('verbas/diarias/<int:pk>/cancelar/', verbas_diarias_actions.cancelar_diaria_action, name='cancelar_diaria_action'),
    path('verbas/reembolsos/novo/', verbas_reembolso_panels.add_reembolso_view, name='add_reembolso'),
    path('verbas/reembolsos/novo/action/', verbas_reembolso_actions.add_reembolso_action, name='add_reembolso_action'),
    path('verbas/jetons/novo/', verbas_jeton_panels.add_jeton_view, name='add_jeton'),
    path('verbas/jetons/novo/action/', verbas_jeton_actions.add_jeton_action, name='add_jeton_action'),
    path('verbas/auxilios/novo/', verbas_auxilio_panels.add_auxilio_view, name='add_auxilio'),
    path('verbas/auxilios/novo/action/', verbas_auxilio_actions.add_auxilio_action, name='add_auxilio_action'),
    path('verbas/reembolsos/<int:pk>/editar/', verbas_reembolso_panels.gerenciar_reembolso_view, name='edit_reembolso'),
    path('verbas/reembolsos/<int:pk>/gerenciar/', verbas_reembolso_panels.gerenciar_reembolso_view, name='gerenciar_reembolso'),
    path('verbas/reembolsos/<int:pk>/solicitar-autorizacao/', verbas_reembolso_actions.solicitar_autorizacao_reembolso_action, name='solicitar_autorizacao_reembolso_action'),
    path('verbas/reembolsos/<int:pk>/autorizar/', verbas_reembolso_actions.autorizar_reembolso_action, name='autorizar_reembolso_action'),
    path('verbas/reembolsos/<int:pk>/cancelar/', verbas_reembolso_actions.cancelar_reembolso_action, name='cancelar_reembolso_action'),
    path('verbas/reembolsos/<int:pk>/comprovantes/registrar/', verbas_reembolso_actions.registrar_comprovante_reembolso_action, name='registrar_comprovante_reembolso_action'),
    path('verbas/jetons/<int:pk>/editar/', verbas_jeton_panels.gerenciar_jeton_view, name='edit_jeton'),
    path('verbas/jetons/<int:pk>/gerenciar/', verbas_jeton_panels.gerenciar_jeton_view, name='gerenciar_jeton'),
    path('verbas/jetons/<int:pk>/solicitar-autorizacao/', verbas_jeton_actions.solicitar_autorizacao_jeton_action, name='solicitar_autorizacao_jeton_action'),
    path('verbas/jetons/<int:pk>/autorizar/', verbas_jeton_actions.autorizar_jeton_action, name='autorizar_jeton_action'),
    path('verbas/jetons/<int:pk>/cancelar/', verbas_jeton_actions.cancelar_jeton_action, name='cancelar_jeton_action'),
    path('verbas/auxilios/<int:pk>/editar/', verbas_auxilio_panels.gerenciar_auxilio_view, name='edit_auxilio'),
    path('verbas/auxilios/<int:pk>/gerenciar/', verbas_auxilio_panels.gerenciar_auxilio_view, name='gerenciar_auxilio'),
    path('verbas/auxilios/<int:pk>/solicitar-autorizacao/', verbas_auxilio_actions.solicitar_autorizacao_auxilio_action, name='solicitar_autorizacao_auxilio_action'),
    path('verbas/auxilios/<int:pk>/autorizar/', verbas_auxilio_actions.autorizar_auxilio_action, name='autorizar_auxilio_action'),
    path('verbas/auxilios/<int:pk>/cancelar/', verbas_auxilio_actions.cancelar_auxilio_action, name='cancelar_auxilio_action'),
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
