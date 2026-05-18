"""URLs do núcleo do sistema: home, processos, pagamentos e contingências."""

from django.urls import path

from apps.pagamentos import imports as pagamentos_imports
from apps.pagamentos.views import api_views as pagamentos_api_views
from apps.pagamentos.views import auditing as pagamentos_auditing_views
from apps.pagamentos.views import pdf as pagamentos_pdf_views
from apps.pagamentos.views import security as pagamentos_security_views
from apps.pagamentos.views.payment.autorizacao import (
    actions as payment_autorizacao_actions,
)
from apps.pagamentos.views.payment.autorizacao import (
    panels as payment_autorizacao_panels,
)
from apps.pagamentos.views.payment.contas_a_pagar import (
    actions as payment_contas_actions,
)
from apps.pagamentos.views.payment.contas_a_pagar import apis as payment_contas_apis
from apps.pagamentos.views.payment.contas_a_pagar import panels as payment_contas_panels
from apps.pagamentos.views.payment.lancamento import (
    actions as payment_lancamento_actions,
)
from apps.pagamentos.views.payment.lancamento import panels as payment_lancamento_panels
from apps.pagamentos.views.post_payment.arquivamento import (
    actions as post_payment_arquivamento_actions,
)
from apps.pagamentos.views.post_payment.arquivamento import (
    panels as post_payment_arquivamento_panels,
)
from apps.pagamentos.views.post_payment.arquivamento import (
    reviews as post_payment_arquivamento_reviews,
)
from apps.pagamentos.views.post_payment.conferencia import (
    actions as post_payment_conferencia_actions,
)
from apps.pagamentos.views.post_payment.conferencia import (
    panels as post_payment_conferencia_panels,
)
from apps.pagamentos.views.post_payment.conferencia import (
    reviews as post_payment_conferencia_reviews,
)
from apps.pagamentos.views.post_payment.conselho import (
    actions as post_payment_conselho_actions,
)
from apps.pagamentos.views.post_payment.conselho import (
    panels as post_payment_conselho_panels,
)
from apps.pagamentos.views.post_payment.conselho import pdf as post_payment_conselho_pdf
from apps.pagamentos.views.post_payment.conselho import (
    reviews as post_payment_conselho_reviews,
)
from apps.pagamentos.views.post_payment.contabilizacao import (
    actions as post_payment_contabilizacao_actions,
)
from apps.pagamentos.views.post_payment.contabilizacao import (
    panels as post_payment_contabilizacao_panels,
)
from apps.pagamentos.views.post_payment.contabilizacao import (
    reviews as post_payment_contabilizacao_reviews,
)
from apps.pagamentos.views.post_payment.reunioes import (
    actions as post_payment_reunioes_actions,
)
from apps.pagamentos.views.post_payment.reunioes import (
    panels as post_payment_reunioes_panels,
)
from apps.pagamentos.views.pre_payment.cadastro import (
    actions as pre_payment_cadastro_actions,
)
from apps.pagamentos.views.pre_payment.cadastro import apis as pre_payment_cadastro_apis
from apps.pagamentos.views.pre_payment.cadastro import (
    panels as pre_payment_cadastro_panels,
)
from apps.pagamentos.views.pre_payment.empenho import actions as pre_payment_actions
from apps.pagamentos.views.pre_payment.empenho import apis as pre_payment_empenho_apis
from apps.pagamentos.views.pre_payment.empenho import panels as pre_payment_panels
from apps.pagamentos.views.pre_payment.liquidacoes import (
    actions as pre_payment_liquidacoes_actions,
)
from apps.pagamentos.views.pre_payment.liquidacoes import (
    panels as pre_payment_liquidacoes_panels,
)
from apps.pagamentos.views.support import reports as relatorio_views
from apps.pagamentos.views.support import signatures as assinatura_views
from apps.pagamentos.views.support.cancelamento import (
    cancelar_processo_action,
    cancelar_processo_spoke_view,
)
from apps.pagamentos.views.support.contas_fixas import actions as conta_actions
from apps.pagamentos.views.support.contas_fixas import panels as conta_panels
from apps.pagamentos.views.support.contingencia.actions import (
    add_contingencia_action,
    analisar_contingencia_action,
)
from apps.pagamentos.views.support.contingencia.panels import (
    add_contingencia_view,
    painel_contingencias_view,
)
from apps.pagamentos.views.support.core import home_page, process_detail_view
from apps.pagamentos.views.support.devolucao import (
    painel_devolucoes_view,
    registrar_devolucao_action,
    registrar_devolucao_view,
)
from apps.pagamentos.views.support.pendencia import (
    atualizar_pendencias_lote_action,
    painel_pendencias_view,
)
from apps.pagamentos.views.support.sync import pagamentos as pagamentos_sync_views

# Adicionamos "pagamentos" como app_name (não mandatório na raiz, mas ideal em modularização)
app_name = 'pagamentos'

urlpatterns = [
    # Core
    path('', home_page, name='home_detail'),
    path('processo/<int:pk>/', process_detail_view, name='process_detail'),
    
    # Pre-payment Cadastro (Processos)
    path('adicionar/', pre_payment_cadastro_panels.add_process_view, name='processo_create'),
    path('adicionar/action/', pre_payment_cadastro_actions.add_process_action, name='add_process_action'),
    path('processo/<int:pk>/editar/', pre_payment_cadastro_panels.editar_processo, name='processo_edit_detail'),
    path('processo/<int:pk>/editar/capa/', pre_payment_cadastro_panels.editar_processo_capa_view, name='processo_capa_detail'),
    path('processo/<int:pk>/editar/capa/action/', pre_payment_cadastro_actions.editar_processo_capa_action, name='editar_processo_capa_action'),
    path('processo/<int:pk>/editar/documentos/', pre_payment_cadastro_panels.editar_processo_documentos_view, name='processo_documentos_detail'),
    path('processo/<int:pk>/editar/documentos/action/', pre_payment_cadastro_actions.editar_processo_documentos_action, name='editar_processo_documentos_action'),
    path('processo/<int:pk>/editar/documentos/<int:documento_id>/extrair-codigo-barras/action/', pre_payment_cadastro_actions.extrair_codigo_barras_documento_action, name='extrair_codigo_barras_documento_action'),
    path('processo/<int:pk>/editar/documentos/extrair-codigos-barras-lote/action/', pre_payment_cadastro_actions.extrair_codigos_barras_lote_action, name='extrair_codigos_barras_lote_action'),
    path('processo/<int:pk>/editar/pendencias/', pre_payment_cadastro_panels.editar_processo_pendencias_view, name='processo_pendencias_detail'),
    path('processo/<int:pk>/editar/pendencias/action/', pre_payment_cadastro_actions.editar_processo_pendencias_action, name='editar_processo_pendencias_action'),
    path('processo/<int:processo_id>/pdf/', pagamentos_pdf_views.visualizar_pdf_processo, name='processo_pdf_detail'),
    path('api/processo/<int:pk>/extrair-codigos-barras/', payment_contas_apis.api_extrair_codigos_barras_processo, name='api_extrair_codigos_barras_processo'),
    path('api/extrair-codigos-barras-upload/', pre_payment_cadastro_apis.api_extrair_codigos_barras_upload, name='api_extrair_codigos_barras_upload'),

    # Despesas e Contas
    path('contas-a-pagar/', payment_contas_panels.contas_a_pagar, name='contas_a_pagar_list'),
    path('a-empenhar/', pre_payment_panels.a_empenhar_view, name='a_empenhar_list'),
    path('a-empenhar/registrar-empenho/action/', pre_payment_actions.registrar_empenho_action, name='registrar_empenho_action'),
    path('api/extrair-dados-empenho/', pre_payment_empenho_apis.api_extrair_dados_empenho, name='api_extrair_dados_empenho'),
    path('processos/liquidacoes/', pre_payment_liquidacoes_panels.painel_liquidacoes_view, name='liquidacoes_list'),
    path('processo/<int:pk>/avancar-para-pagamento/action/', pre_payment_liquidacoes_actions.avancar_para_pagamento_action, name='avancar_para_pagamento_action'),

    # Contas fixas (do antigo backoffice)
    path('importar-siscac/template-contas/', pagamentos_imports.download_template_csv_contas, name='template_csv_contas_detail'),
    path('contas-fixas/', conta_panels.painel_contas_fixas_view, name='contas_fixas_list'),
    path('contas-fixas/nova/', conta_panels.add_conta_fixa_view, name='conta_fixa_create'),
    path('contas-fixas/nova/action/', conta_actions.add_conta_fixa_action, name='add_conta_fixa_action'),
    path('contas-fixas/<int:pk>/editar/', conta_panels.edit_conta_fixa_view, name='conta_fixa_edit_detail'),
    path('contas-fixas/<int:pk>/editar/action/', conta_actions.edit_conta_fixa_action, name='edit_conta_fixa_action'),
    path('contas-fixas/<int:pk>/excluir/action/', conta_actions.excluir_conta_fixa_action, name='excluir_conta_fixa_action'),
    path('contas-fixas/<int:fatura_id>/vincular/action/', conta_actions.vincular_processo_fatura_action, name='vincular_processo_fatura_action'),

    # Relatórios e Assinaturas (do antigo backoffice)
    path('relatorios/', relatorio_views.painel_relatorios_view, name='relatorios_list'),
    path('relatorios/documentos-gerados/', relatorio_views.painel_relatorios_view, name='relatorio_documentos_gerados_list'),
    path('assinaturas/', assinatura_views.painel_assinaturas_view, name='assinaturas_list'),
    path('assinaturas/disparar/<int:assinatura_id>/action/', assinatura_views.disparar_assinatura_view, name='disparar_assinatura_action'),

    # Conferência e Autorização
    path('processos/conferencia/', post_payment_conferencia_panels.painel_conferencia_view, name='conferencia_list'),
    path('processos/conferencia/iniciar/action/', post_payment_conferencia_actions.iniciar_conferencia_action, name='iniciar_conferencia_action'),
    path('processos/conferencia/<int:pk>/revisar/', post_payment_conferencia_reviews.conferencia_processo_view, name='conferencia_processo_detail'),
    path('processos/conferencia/<int:pk>/aprovar/action/', post_payment_conferencia_actions.aprovar_conferencia_action, name='aprovar_conferencia_action'),
    path('processos/enviar-autorizacao/action/', payment_contas_actions.enviar_para_autorizacao_action, name='enviar_para_autorizacao_action'),
    path('processos/autorizacao/', payment_autorizacao_panels.painel_autorizacao_view, name='painel_autorizacao'),
    path('processos/autorizar-pagamento/action/', payment_autorizacao_actions.autorizar_pagamento, name='autorizar_pagamento_action'),
    path('processos/autorizacao/<int:pk>/recusar/action/', payment_autorizacao_actions.recusar_autorizacao_action, name='recusar_autorizacao_action'),

    # Contabilização
    path('processos/contabilizacao/', post_payment_contabilizacao_panels.painel_contabilizacao_view, name='contabilizacao_list'),
    path('processos/contabilizacao/iniciar/action/', post_payment_contabilizacao_actions.iniciar_contabilizacao_action, name='iniciar_contabilizacao_action'),
    path('processos/contabilizacao/<int:pk>/revisar/', post_payment_contabilizacao_reviews.contabilizacao_processo_view, name='contabilizacao_processo_detail'),
    path('processos/contabilizacao/<int:pk>/aprovar/action/', post_payment_contabilizacao_actions.aprovar_contabilizacao_action, name='aprovar_contabilizacao_action'),
    path('processos/contabilizacao/<int:pk>/recusar/action/', post_payment_contabilizacao_actions.recusar_contabilizacao_action, name='recusar_contabilizacao_action'),

    # Conselho e Reuniões
    path('processos/conselho/', post_payment_conselho_panels.painel_conselho_view, name='conselho_list'),
    path('processos/conselho/<int:pk>/revisar/', post_payment_conselho_reviews.conselho_processo_view, name='conselho_processo_detail'),
    path('processos/conselho/<int:pk>/aprovar/action/', post_payment_conselho_actions.aprovar_conselho_action, name='aprovar_conselho_action'),
    path('processos/conselho/<int:pk>/recusar/action/', post_payment_conselho_actions.recusar_conselho_action, name='recusar_conselho_action'),
    path('processos/conselho/reunioes/', post_payment_reunioes_panels.gerenciar_reunioes_view, name='reunioes_list'),
    path('processos/conselho/reunioes/criar/action/', post_payment_reunioes_actions.gerenciar_reunioes_action, name='gerenciar_reunioes_action'),
    path('processos/conselho/reunioes/<int:reuniao_id>/montar-pauta/', post_payment_reunioes_panels.montar_pauta_reuniao_view, name='montar_pauta_reuniao_detail'),
    path('processos/conselho/reunioes/<int:reuniao_id>/montar-pauta/adicionar/action/', post_payment_reunioes_actions.montar_pauta_reuniao_action, name='montar_pauta_reuniao_action'),
    path('processos/conselho/reunioes/<int:reuniao_id>/analisar/', post_payment_reunioes_panels.analise_reuniao_view, name='analise_reuniao_detail'),
    path('processos/conselho/reunioes/<int:reuniao_id>/iniciar/action/', post_payment_reunioes_actions.iniciar_conselho_reuniao_action, name='iniciar_conselho_reuniao_action'),

    # Arquivamento
    path('processos/arquivamento/', post_payment_arquivamento_panels.painel_arquivamento_view, name='arquivamento_list'),
    path('processos/arquivamento/<int:pk>/aprovar/', post_payment_arquivamento_reviews.arquivar_processo_view, name='arquivar_processo_detail'),
    path('processos/arquivamento/<int:pk>/executar/action/', post_payment_arquivamento_actions.arquivar_processo_action, name='arquivar_processo_action'),

    # Suporte, Lançamentos, Pendências, APIs Extras
    path('pendencias/', painel_pendencias_view, name='pendencias_list'),
    path('pendencias/action/', atualizar_pendencias_lote_action, name='atualizar_pendencias_lote_action'),
    path('api/documentos-por-pagamento/', pre_payment_cadastro_apis.api_tipos_documento_por_pagamento, name='api_documentos_pagamento'),
    path('api/detalhes-pagamento/', pagamentos_api_views.api_detalhes_pagamento, name='api_detalhes_pagamento'),
    path('processos/separar-lancamento/action/', payment_lancamento_actions.separar_para_lancamento_bancario_action, name='separar_para_lancamento_bancario_action'),
    path('processos/lancamento-bancario/', payment_lancamento_panels.lancamento_bancario, name='lancamento_bancario_list'),
    path('processos/marcar-lancado/action/', payment_lancamento_actions.marcar_como_lancado_action, name='marcar_como_lancado_action'),
    path('processos/desmarcar-lancamento/action/', payment_lancamento_actions.desmarcar_lancamento_action, name='desmarcar_lancamento_action'),
    path('api/processo/<int:processo_id>/documentos/', pagamentos_auditing_views.api_documentos_processo, name='api_documentos_processo'),
    path('auditoria/', pagamentos_auditing_views.auditoria_view, name='auditoria_list'),

    # Contingências e Devoluções e Cancelamento
    path('contingencias/', painel_contingencias_view, name='contingencias_list'),
    path('contingencias/nova/', add_contingencia_view, name='contingencia_create'),
    path('contingencias/nova/enviar/action/', add_contingencia_action, name='add_contingencia_action'),
    path('contingencias/<int:pk>/analisar/action/', analisar_contingencia_action, name='analisar_contingencia_action'),
    path('api/processo_detalhes/', pagamentos_auditing_views.api_processo_detalhes, name='api_processo_detalhes'),
    path('processo/<int:pk>/autorizacao-pagamento/', pagamentos_pdf_views.gerar_autorizacao_pagamento_view, name='autorizacao_pagamento_pdf_detail'),
    path('processo/<int:pk>/parecer-conselho/', post_payment_conselho_pdf.gerar_parecer_conselho_view, name='parecer_conselho_pdf_detail'),
    path('pagamentos/sincronizar-siscac/', pagamentos_sync_views.sincronizar_siscac, name='sincronizar_siscac'),
    path('pagamentos/sincronizar-siscac/manual/action/', pagamentos_sync_views.sincronizar_siscac_manual_action, name='sincronizar_siscac_manual_action'),
    path('pagamentos/sincronizar-siscac/auto/action/', pagamentos_sync_views.sincronizar_siscac_auto_action, name='sincronizar_siscac_auto_action'),
    path('documentos/secure/<str:tipo_documento>/<int:documento_id>/', pagamentos_security_views.download_arquivo_seguro, name='arquivo_seguro_detail'),
    path('processo/<int:pk>/cancelar/', cancelar_processo_spoke_view, name='cancelar_processo_spoke_detail'),
    path('processo/<int:pk>/cancelar/confirmar/action/', cancelar_processo_action, name='cancelar_processo_action'),
    path('processo/<int:processo_id>/devolucao/', registrar_devolucao_view, name='devolucao_create'),
    path('processo/<int:processo_id>/devolucao/salvar/action/', registrar_devolucao_action, name='registrar_devolucao_action'),
    path('devolucoes/', painel_devolucoes_view, name='devolucoes_list'),
]
