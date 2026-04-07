from django.urls import path

from processos.views.fluxo import api_views as fluxo_api_views
from processos.views.fluxo import auditing as fluxo_auditing_views
from processos.views.fluxo import siscac_processo_sync as fluxo_sync_views
from processos.views.fluxo import security as fluxo_security_views
from processos.views.fluxo import support_views as fluxo_support_views
from processos.views.fluxo.payment import actions as payment_actions
from processos.views.fluxo.payment import panels as payment_panels
from processos.views.fluxo.post_payment import actions as post_payment_actions
from processos.views.fluxo.post_payment import panels as post_payment_panels
from processos.views.fluxo.post_payment import reviews as post_payment_reviews
from processos.views.fluxo.pre_payment import actions as pre_payment_actions
from processos.views.fluxo.pre_payment import forms as pre_payment_forms
from processos.views.fluxo.pre_payment import panels as pre_payment_panels

urlpatterns = [
    path('', fluxo_support_views.home_page, name='home_page'),
    path('adicionar/', pre_payment_forms.add_process_view, name='add_process'),
    path('processo/<int:pk>/editar/', pre_payment_forms.editar_processo, name='editar_processo'),
    path('processo/<int:pk>/editar/capa/', pre_payment_forms.editar_processo_capa_view, name='editar_processo_capa'),
    path('processo/<int:pk>/editar/documentos/', pre_payment_forms.editar_processo_documentos_view, name='editar_processo_documentos'),
    path('processo/<int:pk>/editar/pendencias/', pre_payment_forms.editar_processo_pendencias_view, name='editar_processo_pendencias'),
    path('processo/<int:processo_id>/pdf/', fluxo_api_views.visualizar_pdf_processo, name='visualizar_pdf_processo'),
    path('contas-a-pagar/', payment_panels.contas_a_pagar, name='contas_a_pagar'),
    path('api/processo/<int:pk>/extrair-codigos-barras/', fluxo_api_views.api_extrair_codigos_barras_processo, name='api_extrair_codigos_barras_processo'),
    path('api/extrair-codigos-barras-upload/', fluxo_api_views.api_extrair_codigos_barras_upload, name='api_extrair_codigos_barras_upload'),
    path('a-empenhar/', pre_payment_panels.a_empenhar_view, name='a_empenhar'),
    path('a-empenhar/registrar-empenho/', pre_payment_actions.registrar_empenho_action, name='registrar_empenho_action'),
    path('api/extrair-dados-empenho/', fluxo_api_views.api_extrair_dados_empenho, name='api_extrair_dados_empenho'),
    path('processo/<int:pk>/avancar-para-pagamento/', pre_payment_actions.avancar_para_pagamento_view, name='avancar_para_pagamento'),
    path('processos/conferencia/', post_payment_panels.painel_conferencia_view, name='painel_conferencia'),
    path('processos/conferencia/iniciar/', post_payment_actions.iniciar_conferencia_view, name='iniciar_conferencia'),
    path('processos/conferencia/<int:pk>/revisar/', post_payment_reviews.conferencia_processo_view, name='conferencia_processo'),
    path('processos/conferencia/<int:pk>/aprovar/', post_payment_actions.aprovar_conferencia_view, name='aprovar_conferencia'),
    path('processos/enviar-autorizacao/', payment_actions.enviar_para_autorizacao, name='enviar_para_autorizacao'),
    path('processos/autorizacao/', payment_panels.painel_autorizacao_view, name='painel_autorizacao'),
    path('processos/autorizar-pagamento/', payment_actions.autorizar_pagamento, name='autorizar_pagamento'),
    path('processos/autorizacao/<int:pk>/recusar/', payment_actions.recusar_autorizacao_view, name='recusar_autorizacao'),
    path('processos/contabilizacao/', post_payment_panels.painel_contabilizacao_view, name='painel_contabilizacao'),
    path('processos/contabilizacao/iniciar/', post_payment_actions.iniciar_contabilizacao_view, name='iniciar_contabilizacao'),
    path('processos/contabilizacao/<int:pk>/revisar/', post_payment_reviews.contabilizacao_processo_view, name='contabilizacao_processo'),
    path('processos/contabilizacao/<int:pk>/aprovar/', post_payment_actions.aprovar_contabilizacao_view, name='aprovar_contabilizacao'),
    path('processos/contabilizacao/<int:pk>/recusar/', post_payment_actions.recusar_contabilizacao_view, name='recusar_contabilizacao'),
    path('processos/conselho/', post_payment_panels.painel_conselho_view, name='painel_conselho'),
    path('processos/conselho/<int:pk>/revisar/', post_payment_reviews.conselho_processo_view, name='conselho_processo'),
    path('processos/conselho/<int:pk>/aprovar/', post_payment_actions.aprovar_conselho_view, name='aprovar_conselho'),
    path('processos/conselho/<int:pk>/recusar/', post_payment_actions.recusar_conselho_view, name='recusar_conselho'),
    path('processos/conselho/reunioes/', post_payment_panels.gerenciar_reunioes_view, name='gerenciar_reunioes'),
    path('processos/conselho/reunioes/criar/', post_payment_actions.gerenciar_reunioes_action, name='gerenciar_reunioes_action'),
    path('processos/conselho/reunioes/<int:reuniao_id>/montar-pauta/', post_payment_panels.montar_pauta_reuniao_view, name='montar_pauta_reuniao'),
    path('processos/conselho/reunioes/<int:reuniao_id>/montar-pauta/adicionar/', post_payment_actions.montar_pauta_reuniao_action, name='montar_pauta_reuniao_action'),
    path('processos/conselho/reunioes/<int:reuniao_id>/analisar/', post_payment_panels.analise_reuniao_view, name='analise_reuniao'),
    path('processos/conselho/reunioes/<int:reuniao_id>/iniciar/', post_payment_actions.iniciar_conselho_reuniao_view, name='iniciar_conselho_reuniao'),
    path('processos/arquivamento/', post_payment_panels.painel_arquivamento_view, name='painel_arquivamento'),
    path('processos/arquivamento/<int:pk>/aprovar/', post_payment_reviews.arquivar_processo_view, name='arquivar_processo'),
    path('processos/arquivamento/<int:pk>/executar/', post_payment_actions.arquivar_processo_action, name='arquivar_processo_action'),
    path('pendencias/', fluxo_support_views.painel_pendencias_view, name='painel_pendencias'),
    path('api/documentos-por-pagamento/', fluxo_api_views.api_tipos_documento_por_pagamento, name='api_documentos_pagamento'),
    path('api/detalhes-pagamento/', fluxo_api_views.api_detalhes_pagamento, name='api_detalhes_pagamento'),
    path('processos/separar-lancamento/', payment_actions.separar_para_lancamento_bancario, name='separar_para_lancamento_bancario'),
    path('processos/lancamento-bancario/', payment_panels.lancamento_bancario, name='lancamento_bancario'),
    path('processos/marcar-lancado/', payment_actions.marcar_como_lancado, name='marcar_como_lancado'),
    path('processos/desmarcar-lancamento/', payment_actions.desmarcar_lancamento, name='desmarcar_lancamento'),
    path('api/processo/<int:processo_id>/documentos/', fluxo_auditing_views.api_documentos_processo, name='api_documentos_processo'),
    path('auditoria/', fluxo_auditing_views.auditoria_view, name='auditoria'),
    path('contingencias/', fluxo_support_views.painel_contingencias_view, name='painel_contingencias'),
    path('contingencias/nova/', fluxo_support_views.add_contingencia_view, name='add_contingencia'),
    path('contingencias/nova/enviar/', fluxo_support_views.add_contingencia_action, name='add_contingencia_action'),
    path('contingencias/<int:pk>/analisar/', fluxo_support_views.analisar_contingencia_view, name='analisar_contingencia'),
    path('api/processo_detalhes/', fluxo_auditing_views.api_processo_detalhes, name='api_processo_detalhes'),
    path('processo/<int:pk>/autorizacao-pagamento/', fluxo_api_views.gerar_autorizacao_pagamento_view, name='gerar_autorizacao_pagamento'),
    path('processo/<int:pk>/parecer-conselho/', post_payment_reviews.gerar_parecer_conselho_view, name='gerar_parecer_conselho'),
    path('fluxo/sincronizar-siscac/', fluxo_sync_views.sincronizar_siscac, name='sincronizar_siscac'),
    path('fluxo/sincronizar-siscac/manual/', fluxo_sync_views.sincronizar_siscac_manual_action, name='sincronizar_siscac_manual_action'),
    path('fluxo/sincronizar-siscac/auto/', fluxo_sync_views.sincronizar_siscac_auto_action, name='sincronizar_siscac_auto_action'),
    path('documentos/secure/<str:tipo_documento>/<int:documento_id>/', fluxo_security_views.download_arquivo_seguro, name='download_arquivo_seguro'),
    path('processo/<int:pk>/', fluxo_support_views.process_detail_view, name='process_detail'),
    path('processo/<int:processo_id>/devolucao/', fluxo_support_views.registrar_devolucao_view, name='registrar_devolucao'),
    path('processo/<int:processo_id>/devolucao/salvar/', fluxo_support_views.registrar_devolucao_action, name='registrar_devolucao_action'),
    path('devolucoes/', fluxo_support_views.painel_devolucoes_view, name='painel_devolucoes'),
]
