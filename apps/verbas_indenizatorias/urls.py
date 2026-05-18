"""URLs do domínio de verbas indenizatórias: diárias, auxílios, jetons e reembolsos."""

from django.urls import path

from apps.verbas_indenizatorias.views.auxilios import actions as verbas_auxilio_actions
from apps.verbas_indenizatorias.views.auxilios import panels as verbas_auxilio_panels
from apps.verbas_indenizatorias.views.diarias import actions as verbas_diarias_actions
from apps.verbas_indenizatorias.views.diarias import apis as verbas_diarias_apis
from apps.verbas_indenizatorias.views.diarias import panels as verbas_diarias_panels
from apps.verbas_indenizatorias.views.diarias import pdf as verbas_diarias_pdf
from apps.verbas_indenizatorias.views.diarias.support.contingencia import (
    actions as contingencia_actions,
)
from apps.verbas_indenizatorias.views.diarias.support.contingencia import (
    panels as contingencia_panels,
)
from apps.verbas_indenizatorias.views.diarias.support.devolucao import (
    actions as devolucao_actions,
)
from apps.verbas_indenizatorias.views.diarias.support.devolucao import (
    panels as devolucao_panels,
)
from apps.verbas_indenizatorias.views.diarias.support.imports import (
    actions as verbas_diarias_imports_actions,
)
from apps.verbas_indenizatorias.views.diarias.support.imports import (
    panels as verbas_diarias_imports_panels,
)
from apps.verbas_indenizatorias.views.diarias.support.sync import (
    actions as verbas_diarias_sync_actions,
)
from apps.verbas_indenizatorias.views.diarias.support.sync import (
    panels as verbas_diarias_sync_panels,
)
from apps.verbas_indenizatorias.views.jetons import actions as verbas_jeton_actions
from apps.verbas_indenizatorias.views.jetons import panels as verbas_jeton_panels
from apps.verbas_indenizatorias.views.processo import actions as verbas_actions
from apps.verbas_indenizatorias.views.processo import apis as verbas_apis
from apps.verbas_indenizatorias.views.processo import panels as verbas_panels
from apps.verbas_indenizatorias.views.reembolsos import (
    actions as verbas_reembolso_actions,
)
from apps.verbas_indenizatorias.views.reembolsos import (
    panels as verbas_reembolso_panels,
)
from apps.verbas_indenizatorias.views.solicitacoes import (
    actions as verbas_solicitacoes_actions,
)
from apps.verbas_indenizatorias.views.solicitacoes import (
    panels as verbas_solicitacoes_panels,
)
from apps.verbas_indenizatorias.views.tabela_valores import (
    actions as verbas_tabela_valores_actions,
)
from apps.verbas_indenizatorias.views.tabela_valores import (
    panels as verbas_tabela_valores_panels,
)

app_name = 'verbas_indenizatorias'

urlpatterns = [
    # Processo Verbas
    path('processo/<int:pk>/editar-verbas/', verbas_panels.editar_processo_verbas_view, name='editar_processo_verbas_detail'),
    path('processo/<int:pk>/editar-verbas/capa/', verbas_panels.editar_processo_verbas_capa_view, name='editar_processo_verbas_capa_detail'),
    path('processo/<int:pk>/editar-verbas/capa/action/', verbas_actions.editar_processo_verbas_capa_action, name='editar_processo_verbas_capa_action'),
    path('processo/<int:pk>/editar-verbas/pendencias/', verbas_panels.editar_processo_verbas_pendencias_view, name='editar_processo_verbas_pendencias_detail'),
    path('processo/<int:pk>/editar-verbas/pendencias/action/', verbas_actions.editar_processo_verbas_pendencias_action, name='editar_processo_verbas_pendencias_action'),
    path('processo/<int:pk>/editar-verbas/itens/', verbas_panels.editar_processo_verbas_itens_view, name='editar_processo_verbas_itens_detail'),
    path('processo/<int:pk>/editar-verbas/documentos/', verbas_panels.editar_processo_verbas_documentos_view, name='editar_processo_verbas_documentos_detail'),
    path('processo/<int:pk>/editar-verbas/documentos/action/', verbas_actions.editar_processo_verbas_documentos_action, name='editar_processo_verbas_documentos_action'),
    path('api/verba/<str:tipo_verba>/<int:pk>/add-documento/', verbas_apis.api_add_documento_verba, name='api_add_documento_verba'),

    # Verbas Panel & Lists
    path('', verbas_panels.verbas_panel_view, name='verbas_list'),
    path('diarias/', verbas_diarias_panels.diarias_list_view, name='diarias_list'),
    path('reembolsos/', verbas_reembolso_panels.reembolsos_list_view, name='reembolsos_list'),
    path('jetons/', verbas_jeton_panels.jetons_list_view, name='jetons_list'),
    path('auxilios/', verbas_auxilio_panels.auxilios_list_view, name='auxilios_list'),
    path('agrupar/<str:tipo_verba>/', verbas_actions.agrupar_verbas_view, name='agrupar_verbas_detail'),

    # Tabela de Valores
    path('tabela-valores-unitarios/', verbas_tabela_valores_panels.tabela_valores_unitarios_list_view, name='tabela_valores_unitarios_list'),
    path('tabela-valores-unitarios/novo/', verbas_tabela_valores_panels.add_tabela_valor_unitario_view, name='tabela_valor_unitario_create'),
    path('tabela-valores-unitarios/novo/action/', verbas_tabela_valores_actions.add_tabela_valor_unitario_action, name='add_tabela_valor_unitario_action'),
    path('tabela-valores-unitarios/<int:pk>/editar/', verbas_tabela_valores_panels.edit_tabela_valor_unitario_view, name='tabela_valor_unitario_edit'),
    path('tabela-valores-unitarios/<int:pk>/editar/action/', verbas_tabela_valores_actions.edit_tabela_valor_unitario_action, name='edit_tabela_valor_unitario_action'),

    # Diárias
    path('diarias/nova/', verbas_diarias_panels.add_diaria_view, name='diaria_create'),
    path('diarias/nova/action/', verbas_diarias_actions.add_diaria_action, name='add_diaria_action'),
    path('diarias/nova-assinada/', verbas_diarias_panels.add_diaria_assinada_view, name='diaria_assinada_create'),
    path('diarias/nova-assinada/action/', verbas_diarias_actions.add_diaria_assinada_action, name='add_diaria_assinada_action'),
    path('minhas-prestacoes/', verbas_diarias_panels.minha_prestacao_list_view, name='minha_prestacao_list'),
    path('diarias/<int:pk>/gerenciar/', verbas_diarias_panels.gerenciar_diaria_view, name='diaria_detail'),
    path('diarias/<int:pk>/gerenciar/vinculo/', verbas_diarias_panels.vinculo_diaria_spoke_view, name='vinculo_diaria_spoke'),
    path('diarias/<int:pk>/gerenciar/devolucao/', verbas_diarias_panels.devolucao_diaria_spoke_view, name='devolucao_diaria_spoke'),
    path('diarias/<int:pk>/gerenciar/apostila/', verbas_diarias_panels.apostila_diaria_spoke_view, name='apostila_diaria_spoke'),
    path('diarias/<int:pk>/gerenciar/cancelar/', verbas_diarias_panels.cancelar_diaria_spoke_view, name='cancelar_diaria_spoke'),
    path('diarias/<int:pk>/prestacao/gerenciar/', verbas_diarias_panels.gerenciar_prestacao_view, name='prestacao_diaria_detail'),

    # Autorizações & Processos de Diárias
    path('diarias/autorizar/', verbas_diarias_panels.painel_autorizacao_diarias_view, name='painel_autorizacao_diarias'),
    path('diarias/<int:pk>/comprovantes/registrar/', verbas_diarias_actions.registrar_comprovante_action, name='registrar_comprovante_action'),
    path('diarias/<int:pk>/solicitar-autorizacao/', verbas_diarias_actions.solicitar_autorizacao_diaria_action, name='solicitar_autorizacao_diaria_action'),
    path('diarias/<int:pk>/autorizar/', verbas_diarias_actions.autorizar_diaria_action, name='autorizar_diaria_action'),
    path('diarias/<int:pk>/processo/vincular/action/', verbas_diarias_actions.vincular_diaria_processo_action, name='vincular_diaria_processo_action'),
    path('diarias/<int:pk>/processo/desvincular/action/', verbas_diarias_actions.desvincular_diaria_processo_action, name='desvincular_diaria_processo_action'),
    path('diarias/<int:pk>/prestacao/encerrar/', verbas_diarias_actions.encerrar_prestacao_action, name='encerrar_prestacao_action'),
    path('diarias/<int:pk>/cancelar/action/', verbas_diarias_actions.cancelar_diaria_action, name='cancelar_diaria_action'),

    # Revisão de Prestações
    path('prestacoes/revisar/', verbas_diarias_panels.painel_revisar_prestacoes_view, name='revisar_prestacoes_list'),
    path('prestacoes/revisar/iniciar/', verbas_diarias_actions.iniciar_revisao_prestacoes_action, name='iniciar_revisao_prestacoes_action'),
    path('prestacoes/revisar/sair/', verbas_diarias_actions.sair_revisao_prestacoes_action, name='sair_revisao_prestacoes_action'),
    path('prestacoes/<int:pk>/revisar/', verbas_diarias_panels.revisar_prestacao_view, name='revisar_prestacao_detail'),
    path('prestacoes/<int:pk>/aceitar/', verbas_diarias_actions.aceitar_prestacao_action, name='aceitar_prestacao_action'),

    # Revisão de Solicitações
    path('solicitacoes/revisar/', verbas_solicitacoes_panels.painel_revisar_solicitacoes_view, name='revisar_solicitacoes_list'),
    path('solicitacoes/<str:tipo_verba>/<int:pk>/revisar/', verbas_solicitacoes_panels.revisar_solicitacao_verba_view, name='revisar_solicitacao_verba_detail'),
    path('solicitacoes/<str:tipo_verba>/<int:pk>/aprovar-revisao/', verbas_solicitacoes_actions.aprovar_revisao_solicitacao_action, name='aprovar_revisao_solicitacao_action'),

    # Contingências de Diárias
    path('diarias/contingencias/', contingencia_panels.painel_contingencias_diarias_view, name='contingencias_diarias_list'),
    path('diarias/<int:pk>/contingencia/nova/', contingencia_panels.add_contingencia_diaria_view, name='contingencia_diaria_create'),
    path('diarias/<int:pk>/contingencia/nova/action/', contingencia_actions.add_contingencia_diaria_action, name='add_contingencia_diaria_action'),
    path('contingencias/<int:pk>/analisar/', contingencia_actions.analisar_contingencia_diaria_action, name='analisar_contingencia_diaria_action'),

    # Devoluções de Diárias
    path('diarias/devolucoes/', devolucao_panels.painel_devolucoes_diarias_view, name='devolucoes_diarias_list'),
    path('diarias/<int:pk>/devolucao/nova/', devolucao_panels.registrar_devolucao_diaria_view, name='devolucao_diaria_create'),
    path('diarias/<int:pk>/devolucao/nova/action/', devolucao_actions.registrar_devolucao_diaria_action, name='registrar_devolucao_diaria_action'),

    # Reembolsos
    path('reembolsos/novo/', verbas_reembolso_panels.add_reembolso_view, name='reembolso_create'),
    path('reembolsos/novo/action/', verbas_reembolso_actions.add_reembolso_action, name='add_reembolso_action'),
    path('reembolsos/<int:pk>/editar/', verbas_reembolso_panels.gerenciar_reembolso_view, name='reembolso_edit'),
    path('reembolsos/<int:pk>/gerenciar/', verbas_reembolso_panels.gerenciar_reembolso_view, name='reembolso_detail'),
    path('reembolsos/<int:pk>/gerenciar/cancelar/', verbas_reembolso_panels.cancelar_reembolso_spoke_view, name='cancelar_reembolso_spoke'),
    path('reembolsos/<int:pk>/solicitar-autorizacao/', verbas_reembolso_actions.solicitar_autorizacao_reembolso_action, name='solicitar_autorizacao_reembolso_action'),
    path('reembolsos/<int:pk>/autorizar/', verbas_reembolso_actions.autorizar_reembolso_action, name='autorizar_reembolso_action'),
    path('reembolsos/<int:pk>/cancelar/', verbas_reembolso_actions.cancelar_reembolso_action, name='cancelar_reembolso_action'),
    path('reembolsos/<int:pk>/comprovantes/registrar/', verbas_reembolso_actions.registrar_comprovante_reembolso_action, name='registrar_comprovante_reembolso_action'),

    # Jetons
    path('jetons/novo/', verbas_jeton_panels.add_jeton_view, name='jeton_create'),
    path('jetons/novo/action/', verbas_jeton_actions.add_jeton_action, name='add_jeton_action'),
    path('jetons/<int:pk>/editar/', verbas_jeton_panels.gerenciar_jeton_view, name='jeton_edit'),
    path('jetons/<int:pk>/gerenciar/', verbas_jeton_panels.gerenciar_jeton_view, name='jeton_detail'),
    path('jetons/<int:pk>/gerenciar/cancelar/', verbas_jeton_panels.cancelar_jeton_spoke_view, name='cancelar_jeton_spoke'),
    path('jetons/<int:pk>/solicitar-autorizacao/', verbas_jeton_actions.solicitar_autorizacao_jeton_action, name='solicitar_autorizacao_jeton_action'),
    path('jetons/<int:pk>/autorizar/', verbas_jeton_actions.autorizar_jeton_action, name='autorizar_jeton_action'),
    path('jetons/<int:pk>/cancelar/', verbas_jeton_actions.cancelar_jeton_action, name='cancelar_jeton_action'),

    # Auxílios
    path('auxilios/novo/', verbas_auxilio_panels.add_auxilio_view, name='auxilio_create'),
    path('auxilios/novo/action/', verbas_auxilio_actions.add_auxilio_action, name='add_auxilio_action'),
    path('auxilios/<int:pk>/editar/', verbas_auxilio_panels.gerenciar_auxilio_view, name='auxilio_edit'),
    path('auxilios/<int:pk>/gerenciar/', verbas_auxilio_panels.gerenciar_auxilio_view, name='auxilio_detail'),
    path('auxilios/<int:pk>/gerenciar/cancelar/', verbas_auxilio_panels.cancelar_auxilio_spoke_view, name='cancelar_auxilio_spoke'),
    path('auxilios/<int:pk>/solicitar-autorizacao/', verbas_auxilio_actions.solicitar_autorizacao_auxilio_action, name='solicitar_autorizacao_auxilio_action'),
    path('auxilios/<int:pk>/autorizar/', verbas_auxilio_actions.autorizar_auxilio_action, name='autorizar_auxilio_action'),
    path('auxilios/<int:pk>/cancelar/', verbas_auxilio_actions.cancelar_auxilio_action, name='cancelar_auxilio_action'),

    # APIs e PDFs
    path('api/valor-unitario-diaria/<int:beneficiario_id>/', verbas_diarias_apis.api_valor_unitario_diaria, name='api_valor_unitario_diaria'),
    path('api/diarias-iniciais/<int:beneficiario_id>/', verbas_diarias_apis.api_diarias_iniciais_por_beneficiario, name='api_diarias_iniciais_por_beneficiario'),
    path('diarias/<int:pk>/pcd/', verbas_diarias_pdf.gerar_pcd_view, name='pcd_pdf'),
    path('diarias/<int:pk>/termo-prestacao-contas/', verbas_diarias_pdf.gerar_termo_prestacao_contas_view, name='termo_prestacao_contas_pdf'),

    # Sincronização & Importação
    path('sincronizar-diarias/', verbas_diarias_sync_panels.sincronizar_diarias_view, name='sincronizar_diarias_list'),
    path('sincronizar-diarias/action/', verbas_diarias_sync_actions.sincronizar_diarias_action, name='sincronizar_diarias_action'),
    path('diarias/importar/', verbas_diarias_imports_panels.importar_diarias_view, name='importar_diarias_detail'),
    path('diarias/importar/action/', verbas_diarias_imports_actions.importar_diarias_action, name='importar_diarias_action'),
    path('diarias/template-xlsx/', verbas_diarias_panels.download_template_diarias_xlsx, name='template_diarias_xlsx'),
]