from django.urls import path

from fluxo.views import api_views as fluxo_api_views
from fluxo.views import auditing as fluxo_auditing_views
from fluxo.views import pdf as fluxo_pdf_views
from fluxo.views import security as fluxo_security_views
from fluxo.views.support.core import home_page, process_detail_view
from fluxo.views.support.sync import pagamentos as pagamentos_sync_views
from fluxo.views.support.pendencia import painel_pendencias_view, atualizar_pendencias_lote_action
from fluxo.views.support.contingencia import (
    painel_contingencias_view,
    add_contingencia_view,
    add_contingencia_action,
    analisar_contingencia_action,
)
from fluxo.views.support.devolucao import (
    painel_devolucoes_view,
    registrar_devolucao_view,
    registrar_devolucao_action,
)
from fluxo.views.payment.autorizacao import actions as payment_autorizacao_actions
from fluxo.views.payment.autorizacao import panels as payment_autorizacao_panels
from fluxo.views.payment.contas_a_pagar import actions as payment_contas_actions
from fluxo.views.payment.contas_a_pagar import apis as payment_contas_apis
from fluxo.views.payment.contas_a_pagar import panels as payment_contas_panels
from fluxo.views.payment.lancamento import actions as payment_lancamento_actions
from fluxo.views.payment.lancamento import panels as payment_lancamento_panels
from fluxo.views.post_payment.arquivamento import actions as post_payment_arquivamento_actions
from fluxo.views.post_payment.arquivamento import panels as post_payment_arquivamento_panels
from fluxo.views.post_payment.arquivamento import reviews as post_payment_arquivamento_reviews
from fluxo.views.post_payment.conferencia import actions as post_payment_conferencia_actions
from fluxo.views.post_payment.conferencia import panels as post_payment_conferencia_panels
from fluxo.views.post_payment.conferencia import reviews as post_payment_conferencia_reviews
from fluxo.views.post_payment.conselho import actions as post_payment_conselho_actions
from fluxo.views.post_payment.conselho import panels as post_payment_conselho_panels
from fluxo.views.post_payment.conselho import pdf as post_payment_conselho_pdf
from fluxo.views.post_payment.conselho import reviews as post_payment_conselho_reviews
from fluxo.views.post_payment.contabilizacao import actions as post_payment_contabilizacao_actions
from fluxo.views.post_payment.contabilizacao import panels as post_payment_contabilizacao_panels
from fluxo.views.post_payment.contabilizacao import reviews as post_payment_contabilizacao_reviews
from fluxo.views.post_payment.reunioes import actions as post_payment_reunioes_actions
from fluxo.views.post_payment.reunioes import panels as post_payment_reunioes_panels
from fluxo.views.pre_payment.cadastro import actions as pre_payment_cadastro_actions
from fluxo.views.pre_payment.cadastro import apis as pre_payment_cadastro_apis
from fluxo.views.pre_payment.cadastro import panels as pre_payment_cadastro_panels
from fluxo.views.pre_payment.empenho import actions as pre_payment_actions
from fluxo.views.pre_payment.empenho import apis as pre_payment_empenho_apis
from fluxo.views.pre_payment.empenho import panels as pre_payment_panels
from fluxo.views.pre_payment.liquidacoes import actions as pre_payment_liquidacoes_actions

urlpatterns = [
    path('', home_page, name='home_page'),
    path('adicionar/', pre_payment_cadastro_panels.add_process_view, name='add_process'),
    path('adicionar/action/', pre_payment_cadastro_actions.add_process_action, name='add_process_action'),
    path('processo/<int:pk>/editar/', pre_payment_cadastro_panels.editar_processo, name='editar_processo'),
    path('processo/<int:pk>/editar/capa/', pre_payment_cadastro_panels.editar_processo_capa_view, name='editar_processo_capa'),
    path('processo/<int:pk>/editar/capa/action/', pre_payment_cadastro_actions.editar_processo_capa_action, name='editar_processo_capa_action'),
    path('processo/<int:pk>/editar/documentos/', pre_payment_cadastro_panels.editar_processo_documentos_view, name='editar_processo_documentos'),
    path('processo/<int:pk>/editar/documentos/action/', pre_payment_cadastro_actions.editar_processo_documentos_action, name='editar_processo_documentos_action'),
    path('processo/<int:pk>/editar/pendencias/', pre_payment_cadastro_panels.editar_processo_pendencias_view, name='editar_processo_pendencias'),
    path('processo/<int:pk>/editar/pendencias/action/', pre_payment_cadastro_actions.editar_processo_pendencias_action, name='editar_processo_pendencias_action'),
    path('processo/<int:processo_id>/pdf/', fluxo_pdf_views.visualizar_pdf_processo, name='visualizar_pdf_processo'),
    path('contas-a-pagar/', payment_contas_panels.contas_a_pagar, name='contas_a_pagar'),
    path('api/processo/<int:pk>/extrair-codigos-barras/', payment_contas_apis.api_extrair_codigos_barras_processo, name='api_extrair_codigos_barras_processo'),
    path('api/extrair-codigos-barras-upload/', pre_payment_cadastro_apis.api_extrair_codigos_barras_upload, name='api_extrair_codigos_barras_upload'),
    path('a-empenhar/', pre_payment_panels.a_empenhar_view, name='a_empenhar'),
    path('a-empenhar/registrar-empenho/', pre_payment_actions.registrar_empenho_action, name='registrar_empenho_action'),
    path('api/extrair-dados-empenho/', pre_payment_empenho_apis.api_extrair_dados_empenho, name='api_extrair_dados_empenho'),
    path(
        'processo/<int:pk>/avancar-para-pagamento/',
        pre_payment_liquidacoes_actions.avancar_para_pagamento_action,
        name='avancar_para_pagamento',
    ),
    path('processos/conferencia/', post_payment_conferencia_panels.painel_conferencia_view, name='painel_conferencia'),
    path('processos/conferencia/iniciar/', post_payment_conferencia_actions.iniciar_conferencia_action, name='iniciar_conferencia'),
    path('processos/conferencia/<int:pk>/revisar/', post_payment_conferencia_reviews.conferencia_processo_view, name='conferencia_processo'),
    path('processos/conferencia/<int:pk>/aprovar/', post_payment_conferencia_actions.aprovar_conferencia_action, name='aprovar_conferencia'),
    path('processos/enviar-autorizacao/', payment_contas_actions.enviar_para_autorizacao_action, name='enviar_para_autorizacao'),
    path('processos/autorizacao/', payment_autorizacao_panels.painel_autorizacao_view, name='painel_autorizacao'),
    path('processos/autorizar-pagamento/', payment_autorizacao_actions.autorizar_pagamento, name='autorizar_pagamento'),
    path('processos/autorizacao/<int:pk>/recusar/', payment_autorizacao_actions.recusar_autorizacao_action, name='recusar_autorizacao'),
    path('processos/contabilizacao/', post_payment_contabilizacao_panels.painel_contabilizacao_view, name='painel_contabilizacao'),
    path('processos/contabilizacao/iniciar/', post_payment_contabilizacao_actions.iniciar_contabilizacao_action, name='iniciar_contabilizacao'),
    path('processos/contabilizacao/<int:pk>/revisar/', post_payment_contabilizacao_reviews.contabilizacao_processo_view, name='contabilizacao_processo'),
    path('processos/contabilizacao/<int:pk>/aprovar/', post_payment_contabilizacao_actions.aprovar_contabilizacao_action, name='aprovar_contabilizacao'),
    path('processos/contabilizacao/<int:pk>/recusar/', post_payment_contabilizacao_actions.recusar_contabilizacao_action, name='recusar_contabilizacao'),
    path('processos/conselho/', post_payment_conselho_panels.painel_conselho_view, name='painel_conselho'),
    path('processos/conselho/<int:pk>/revisar/', post_payment_conselho_reviews.conselho_processo_view, name='conselho_processo'),
    path('processos/conselho/<int:pk>/aprovar/', post_payment_conselho_actions.aprovar_conselho_action, name='aprovar_conselho'),
    path('processos/conselho/<int:pk>/recusar/', post_payment_conselho_actions.recusar_conselho_action, name='recusar_conselho'),
    path('processos/conselho/reunioes/', post_payment_reunioes_panels.gerenciar_reunioes_view, name='gerenciar_reunioes'),
    path('processos/conselho/reunioes/criar/', post_payment_reunioes_actions.gerenciar_reunioes_action, name='gerenciar_reunioes_action'),
    path('processos/conselho/reunioes/<int:reuniao_id>/montar-pauta/', post_payment_reunioes_panels.montar_pauta_reuniao_view, name='montar_pauta_reuniao'),
    path('processos/conselho/reunioes/<int:reuniao_id>/montar-pauta/adicionar/', post_payment_reunioes_actions.montar_pauta_reuniao_action, name='montar_pauta_reuniao_action'),
    path('processos/conselho/reunioes/<int:reuniao_id>/analisar/', post_payment_reunioes_panels.analise_reuniao_view, name='analise_reuniao'),
    path('processos/conselho/reunioes/<int:reuniao_id>/iniciar/', post_payment_reunioes_actions.iniciar_conselho_reuniao_action, name='iniciar_conselho_reuniao'),
    path('processos/arquivamento/', post_payment_arquivamento_panels.painel_arquivamento_view, name='painel_arquivamento'),
    path('processos/arquivamento/<int:pk>/aprovar/', post_payment_arquivamento_reviews.arquivar_processo_view, name='arquivar_processo'),
    path('processos/arquivamento/<int:pk>/executar/', post_payment_arquivamento_actions.arquivar_processo_action, name='arquivar_processo_action'),
    path('pendencias/', painel_pendencias_view, name='painel_pendencias'),
    path('pendencias/action/', atualizar_pendencias_lote_action, name='painel_pendencias_action'),
    path('api/documentos-por-pagamento/', pre_payment_cadastro_apis.api_tipos_documento_por_pagamento, name='api_documentos_pagamento'),
    path('api/detalhes-pagamento/', fluxo_api_views.api_detalhes_pagamento, name='api_detalhes_pagamento'),
    path('processos/separar-lancamento/', payment_lancamento_actions.separar_para_lancamento_bancario_action, name='separar_para_lancamento_bancario'),
    path('processos/lancamento-bancario/', payment_lancamento_panels.lancamento_bancario, name='lancamento_bancario'),
    path('processos/marcar-lancado/', payment_lancamento_actions.marcar_como_lancado_action, name='marcar_como_lancado'),
    path('processos/desmarcar-lancamento/', payment_lancamento_actions.desmarcar_lancamento_action, name='desmarcar_lancamento'),
    path('api/processo/<int:processo_id>/documentos/', fluxo_auditing_views.api_documentos_processo, name='api_documentos_processo'),
    path('auditoria/', fluxo_auditing_views.auditoria_view, name='auditoria'),
    path('contingencias/', painel_contingencias_view, name='painel_contingencias'),
    path('contingencias/nova/', add_contingencia_view, name='add_contingencia'),
    path('contingencias/nova/enviar/', add_contingencia_action, name='add_contingencia_action'),
    path('contingencias/<int:pk>/analisar/', analisar_contingencia_action, name='analisar_contingencia'),
    path('api/processo_detalhes/', fluxo_auditing_views.api_processo_detalhes, name='api_processo_detalhes'),
    path('processo/<int:pk>/autorizacao-pagamento/', fluxo_pdf_views.gerar_autorizacao_pagamento_view, name='gerar_autorizacao_pagamento'),
    path('processo/<int:pk>/parecer-conselho/', post_payment_conselho_pdf.gerar_parecer_conselho_view, name='gerar_parecer_conselho'),
    path('fluxo/sincronizar-siscac/', pagamentos_sync_views.sincronizar_siscac, name='sincronizar_siscac'),
    path('fluxo/sincronizar-siscac/manual/', pagamentos_sync_views.sincronizar_siscac_manual_action, name='sincronizar_siscac_manual_action'),
    path('fluxo/sincronizar-siscac/auto/', pagamentos_sync_views.sincronizar_siscac_auto_action, name='sincronizar_siscac_auto_action'),
    path('documentos/secure/<str:tipo_documento>/<int:documento_id>/', fluxo_security_views.download_arquivo_seguro, name='download_arquivo_seguro'),
    path('processo/<int:pk>/', process_detail_view, name='process_detail'),
    path('processo/<int:processo_id>/devolucao/', registrar_devolucao_view, name='registrar_devolucao'),
    path('processo/<int:processo_id>/devolucao/salvar/', registrar_devolucao_action, name='registrar_devolucao_action'),
    path('devolucoes/', painel_devolucoes_view, name='painel_devolucoes'),
]
