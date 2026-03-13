from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from processos.views import home_page, add_process_view, visualizar_pdf_processo, editar_processo, painel_impostos, contas_a_pagar, api_processar_boleto, add_pre_empenho_view, a_empenhar_view, add_credor_view, credores_list_view, diarias_list_view, reembolsos_list_view, jetons_list_view, auxilios_list_view, add_diaria_view, add_reembolso_view, add_jeton_view, add_auxilio_view, verbas_panel_view, agrupar_verbas_view, agrupar_impostos_view, painel_comprovantes_view, api_fatiar_comprovantes, api_vincular_comprovantes, painel_conferencia_view, aprovar_conferencia_view, enviar_para_autorizacao, painel_autorizacao_view, autorizar_pagamento, aprovar_contabilizacao_view, aprovar_conselho_view, arquivar_processo_view, painel_conselho_view, painel_arquivamento_view, painel_contabilizacao_view, painel_suprimentos_view, gerenciar_suprimento_view, fechar_suprimento_view, add_suprimento_view, recusar_conferencia_view, recusar_contabilizacao_view, recusar_autorizacao_view, recusar_conselho_view, api_extrair_nota, api_extracao_universal, api_dados_credor, api_tipos_documento_por_pagamento, painel_pendencias_view, alternar_ateste_nota, painel_liquidacoes_view, triagem_notas_view, api_detalhes_pagamento, separar_para_lancamento_bancario, lancamento_bancario, marcar_como_lancado, desmarcar_lancamento
from processos.ai_views import ai_extraction_page_view, api_testar_extracao

urlpatterns = [
path('admin/', admin.site.urls),

# Rota raiz (Home)
path('', home_page, name='home_page'),
path('adicionar/', add_process_view, name='add_process'),
path('processo/<int:pk>/editar/', editar_processo, name='editar_processo'),
path('processo/<int:processo_id>/pdf/', visualizar_pdf_processo, name='visualizar_pdf_processo'),
path('contas-a-pagar/', contas_a_pagar, name='contas_a_pagar'),
path('testador-ia/', ai_extraction_page_view, name='testador_ia'),
path('api/testar-extracao/', api_testar_extracao, name='api_testar_extracao'),

path('retencao-impostos/', painel_impostos, name='painel_impostos'),
path('api/processar-boleto/', api_processar_boleto, name='api_processar_boleto'),
path('adicionar-pre-empenho/', add_pre_empenho_view, name='add_pre_empenho'),
path('a-empenhar/', a_empenhar_view, name='a_empenhar'),
path('adicionar-credor/', add_credor_view, name='add_credor'),
path('credores/', credores_list_view, name='credores_list'),
path('verbas/diarias/', diarias_list_view, name='diarias_list'),
path('verbas/reembolsos/', reembolsos_list_view, name='reembolsos_list'),
path('verbas/jetons/', jetons_list_view, name='jetons_list'),
path('verbas/auxilios/', auxilios_list_view, name='auxilios_list'),
path('verbas/diarias/nova/', add_diaria_view, name='add_diaria'),
path('verbas/reembolsos/novo/', add_reembolso_view, name='add_reembolso'),
path('verbas/jetons/novo/', add_jeton_view, name='add_jeton'),
path('verbas/auxilios/novo/', add_auxilio_view, name='add_auxilio'),
path('verbas/', verbas_panel_view, name='verbas_panel'),
path('verbas/agrupar/<str:tipo_verba>/', agrupar_verbas_view, name='agrupar_verbas'),
path('impostos/agrupar/', agrupar_impostos_view, name='agrupar_impostos'),
path('processos/comprovantes/', painel_comprovantes_view, name='painel_comprovantes'),
path('api/comprovantes/fatiar/', api_fatiar_comprovantes, name='api_fatiar_comprovantes'),
path('api/comprovantes/vincular/', api_vincular_comprovantes, name='api_vincular_comprovantes'),
path('processos/conferencia/', painel_conferencia_view, name='painel_conferencia'),
path('processos/conferencia/<int:pk>/aprovar/', aprovar_conferencia_view, name='aprovar_conferencia'),
path('processos/enviar-autorizacao/', enviar_para_autorizacao, name='enviar_para_autorizacao'),
path('processos/autorizacao/', painel_autorizacao_view, name='painel_autorizacao'),
path('processos/autorizar-pagamento/', autorizar_pagamento, name='autorizar_pagamento'),
# Contabilização
path('processos/contabilizacao/', painel_contabilizacao_view, name='painel_contabilizacao'),
path('processos/contabilizacao/<int:pk>/aprovar/', aprovar_contabilizacao_view, name='aprovar_contabilizacao'),

# Conselho Fiscal
path('processos/conselho/', painel_conselho_view, name='painel_conselho'),
path('processos/conselho/<int:pk>/aprovar/', aprovar_conselho_view, name='aprovar_conselho'),

# Arquivamento
path('processos/arquivamento/', painel_arquivamento_view, name='painel_arquivamento'),
path('processos/arquivamento/<int:pk>/aprovar/', arquivar_processo_view, name='arquivar_processo'),
path('suprimentos/', painel_suprimentos_view, name='painel_suprimentos'),
path('suprimentos/<int:pk>/gerenciar/', gerenciar_suprimento_view, name='gerenciar_suprimento'),
path('suprimentos/<int:pk>/fechar/', fechar_suprimento_view, name='fechar_suprimento'),
path('suprimentos/novo/', add_suprimento_view, name='add_suprimento'),
path('processos/conferencia/<int:pk>/recusar/', recusar_conferencia_view, name='recusar_conferencia'),
path('processos/contabilizacao/<int:pk>/recusar/', recusar_contabilizacao_view, name='recusar_contabilizacao'),
path('processos/autorizacao/<int:pk>/recusar/', recusar_autorizacao_view, name='recusar_autorizacao'),
path('processos/conselho/<int:pk>/recusar/', recusar_conselho_view, name='recusar_conselho'),
path('api/extrair-nota/', api_extrair_nota, name='api_extrair_nota'),
path('api/extracao-universal/', api_extracao_universal, name='api_extracao_universal'),
path('processos/conselho/', painel_conselho_view, name='painel_conselho'),
path('processos/autorizacao/', painel_autorizacao_view, name='painel_autorizacao'),
path('api/credor/<int:credor_id>/', api_dados_credor, name='api_dados_credor'),
path('api/documentos-por-pagamento/', api_tipos_documento_por_pagamento, name='api_documentos_pagamento'),
path('pendencias/', painel_pendencias_view, name='painel_pendencias'),
path('liquidacoes/', painel_liquidacoes_view, name='painel_liquidacoes'),
path('liquidacoes/atestar/<int:pk>/', alternar_ateste_nota, name='alternar_ateste_nota'),
path('processo/<int:pk>/triagem-notas/', triagem_notas_view, name='triagem_notas'),
path('api/detalhes-pagamento/', api_detalhes_pagamento, name='api_detalhes_pagamento'),
path('processos/separar-lancamento/', separar_para_lancamento_bancario, name='separar_para_lancamento_bancario'),
path('processos/lancamento-bancario/', lancamento_bancario, name='lancamento_bancario'),
path('processos/marcar-lancado/', marcar_como_lancado, name='marcar_como_lancado'),
path('processos/desmarcar-lancamento/', desmarcar_lancamento, name='desmarcar_lancamento'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)