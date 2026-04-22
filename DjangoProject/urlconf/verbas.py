from django.urls import path

from verbas_indenizatorias.views.processo import actions as verbas_actions
from verbas_indenizatorias.views.processo import apis as verbas_apis
from verbas_indenizatorias.views.processo import panels as verbas_panels
from verbas_indenizatorias.views.auxilios import actions as verbas_auxilio_actions
from verbas_indenizatorias.views.auxilios import panels as verbas_auxilio_panels
from verbas_indenizatorias.views.diarias import actions as verbas_diarias_actions
from verbas_indenizatorias.views.diarias import apis as verbas_diarias_apis
from verbas_indenizatorias.views.diarias import imports as verbas_diarias_imports
from verbas_indenizatorias.views.diarias import panels as verbas_diarias_panels
from verbas_indenizatorias.views.diarias import pdf as verbas_diarias_pdf
from verbas_indenizatorias.views.diarias import sync as verbas_diarias_sync
from verbas_indenizatorias.views.diarias.contingencia import panels as contingencia_panels
from verbas_indenizatorias.views.diarias.contingencia import actions as contingencia_actions
from verbas_indenizatorias.views.diarias.devolucao import panels as devolucao_panels
from verbas_indenizatorias.views.diarias.devolucao import actions as devolucao_actions
from verbas_indenizatorias.views.jetons import actions as verbas_jeton_actions
from verbas_indenizatorias.views.jetons import panels as verbas_jeton_panels
from verbas_indenizatorias.views.reembolsos import actions as verbas_reembolso_actions
from verbas_indenizatorias.views.reembolsos import panels as verbas_reembolso_panels

urlpatterns = [
    path('processo/<int:pk>/editar-verbas/', verbas_panels.editar_processo_verbas_view, name='editar_processo_verbas'),
    path('processo/<int:pk>/editar-verbas/capa/', verbas_panels.editar_processo_verbas_capa_view, name='editar_processo_verbas_capa'),
    path('processo/<int:pk>/editar-verbas/capa/action/', verbas_actions.editar_processo_verbas_capa_action, name='editar_processo_verbas_capa_action'),
    path('processo/<int:pk>/editar-verbas/pendencias/', verbas_panels.editar_processo_verbas_pendencias_view, name='editar_processo_verbas_pendencias'),
    path('processo/<int:pk>/editar-verbas/pendencias/action/', verbas_actions.editar_processo_verbas_pendencias_action, name='editar_processo_verbas_pendencias_action'),
    path('processo/<int:pk>/editar-verbas/itens/', verbas_panels.editar_processo_verbas_itens_view, name='editar_processo_verbas_itens'),
    path('processo/<int:pk>/editar-verbas/documentos/', verbas_panels.editar_processo_verbas_documentos_view, name='editar_processo_verbas_documentos'),
    path('processo/<int:pk>/editar-verbas/documentos/action/', verbas_actions.editar_processo_verbas_documentos_action, name='editar_processo_verbas_documentos_action'),
    path('api/verba/<str:tipo_verba>/<int:pk>/add-documento/', verbas_apis.api_add_documento_verba, name='api_add_documento_verba'),
    path('verbas/', verbas_panels.verbas_panel_view, name='verbas_panel'),
    path('verbas/diarias/', verbas_diarias_panels.diarias_list_view, name='diarias_list'),
    path('verbas/reembolsos/', verbas_reembolso_panels.reembolsos_list_view, name='reembolsos_list'),
    path('verbas/jetons/', verbas_jeton_panels.jetons_list_view, name='jetons_list'),
    path('verbas/auxilios/', verbas_auxilio_panels.auxilios_list_view, name='auxilios_list'),
    path('verbas/diarias/nova/', verbas_diarias_panels.add_diaria_view, name='add_diaria'),
    path('verbas/diarias/nova/action/', verbas_diarias_actions.add_diaria_action, name='add_diaria_action'),
    path('verbas/minhas-prestacoes/', verbas_diarias_panels.minha_prestacao_list_view, name='minha_prestacao_list'),
    path('verbas/diarias/<int:pk>/gerenciar/', verbas_diarias_panels.gerenciar_diaria_view, name='gerenciar_diaria'),
    path('verbas/diarias/<int:pk>/gerenciar/vinculo/', verbas_diarias_panels.vinculo_diaria_spoke_view, name='vinculo_diaria_spoke'),
    path('verbas/diarias/<int:pk>/gerenciar/devolucao/', verbas_diarias_panels.devolucao_diaria_spoke_view, name='devolucao_diaria_spoke'),
    path('verbas/diarias/<int:pk>/gerenciar/apostila/', verbas_diarias_panels.apostila_diaria_spoke_view, name='apostila_diaria_spoke'),
    path('verbas/diarias/<int:pk>/gerenciar/liberar-assinatura/', verbas_diarias_panels.liberar_assinatura_diaria_spoke_view, name='liberar_assinatura_diaria_spoke'),
    path('verbas/diarias/<int:pk>/gerenciar/cancelar/', verbas_diarias_panels.cancelar_diaria_spoke_view, name='cancelar_diaria_spoke'),
    path('verbas/diarias/<int:pk>/prestacao/gerenciar/', verbas_diarias_panels.gerenciar_prestacao_view, name='gerenciar_prestacao'),

    path('verbas/diarias/<int:pk>/comprovantes/registrar/', verbas_diarias_actions.registrar_comprovante_action, name='registrar_comprovante_action'),
    path('verbas/diarias/<int:pk>/solicitar-autorizacao/', verbas_diarias_actions.solicitar_autorizacao_diaria_action, name='solicitar_autorizacao_diaria_action'),
    path('verbas/diarias/<int:pk>/autorizar/', verbas_diarias_actions.autorizar_diaria_action, name='autorizar_diaria_action'),
    path('verbas/diarias/<int:pk>/processo/vincular/action/', verbas_diarias_actions.vincular_diaria_processo_action, name='vincular_diaria_processo_action'),
    path('verbas/diarias/<int:pk>/processo/desvincular/action/', verbas_diarias_actions.desvincular_diaria_processo_action, name='desvincular_diaria_processo_action'),
    path('verbas/diarias/<int:pk>/prestacao/encerrar/', verbas_diarias_actions.encerrar_prestacao_action, name='encerrar_prestacao_action'),
    path('verbas/prestacoes/revisar/', verbas_diarias_panels.painel_revisar_prestacoes_view, name='painel_revisar_prestacoes'),
    path('verbas/prestacoes/<int:pk>/revisar/', verbas_diarias_panels.revisar_prestacao_view, name='revisar_prestacao'),
    path('verbas/prestacoes/<int:pk>/aceitar/', verbas_diarias_actions.aceitar_prestacao_action, name='aceitar_prestacao_action'),
    path('verbas/diarias/<int:pk>/liberar-assinatura/action/', verbas_diarias_actions.liberar_para_assinatura_action, name='liberar_para_assinatura_action'),
    path('verbas/diarias/<int:pk>/cancelar/action/', verbas_diarias_actions.cancelar_diaria_action, name='cancelar_diaria_action'),
    path('verbas/solicitacoes/revisar/', verbas_panels.painel_revisar_solicitacoes_view, name='painel_revisar_solicitacoes'),
    path('verbas/solicitacoes/<str:tipo_verba>/<int:pk>/revisar/', verbas_panels.revisar_solicitacao_verba_view, name='revisar_solicitacao_verba'),
    path('verbas/solicitacoes/<str:tipo_verba>/<int:pk>/aprovar-revisao/', verbas_actions.aprovar_revisao_solicitacao_action, name='aprovar_revisao_solicitacao_action'),

    # Contingências de Diárias
    path('verbas/diarias/contingencias/', contingencia_panels.painel_contingencias_diarias_view, name='painel_contingencias_diarias'),
    path('verbas/diarias/<int:pk>/contingencia/nova/', contingencia_panels.add_contingencia_diaria_view, name='add_contingencia_diaria'),
    path('verbas/diarias/<int:pk>/contingencia/nova/action/', contingencia_actions.add_contingencia_diaria_action, name='add_contingencia_diaria_action'),
    path('verbas/contingencias/<int:pk>/analisar/', contingencia_actions.analisar_contingencia_diaria_action, name='analisar_contingencia_diaria_action'),

    # Devoluções de Diárias
    path('verbas/diarias/devolucoes/', devolucao_panels.painel_devolucoes_diarias_view, name='painel_devolucoes_diarias'),
    path('verbas/diarias/<int:pk>/devolucao/nova/', devolucao_panels.registrar_devolucao_diaria_view, name='registrar_devolucao_diaria'),
    path('verbas/diarias/<int:pk>/devolucao/nova/action/', devolucao_actions.registrar_devolucao_diaria_action, name='registrar_devolucao_diaria_action'),

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
    path('api/valor-unitario-diaria/<int:beneficiario_id>/', verbas_diarias_apis.api_valor_unitario_diaria, name='api_valor_unitario_diaria'),
    path('api/diarias-iniciais/<int:beneficiario_id>/', verbas_diarias_apis.api_diarias_iniciais_por_beneficiario, name='api_diarias_iniciais_por_beneficiario'),

    path('verbas/diarias/<int:pk>/pcd/', verbas_diarias_pdf.gerar_pcd_view, name='gerar_pcd'),
    path('verbas/diarias/<int:pk>/termo-prestacao-contas/', verbas_diarias_pdf.gerar_termo_prestacao_contas_view, name='gerar_termo_prestacao_contas'),
    path('verbas/sincronizar-diarias/', verbas_diarias_sync.sincronizar_diarias, name='sincronizar_diarias'),
    path('verbas/diarias/importar/', verbas_diarias_imports.importar_diarias_view, name='importar_diarias'),
    path('verbas/diarias/template-csv/', verbas_diarias_panels.download_template_diarias_csv, name='download_template_diarias_csv'),

]
