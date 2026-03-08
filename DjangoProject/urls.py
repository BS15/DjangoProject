from django.contrib import admin
from django.urls import path
from processos.views import home_page, add_process_view, visualizar_pdf_processo, editar_processo, painel_impostos, contas_a_pagar, api_processar_boleto, add_pre_empenho_view, a_empenhar_view, add_credor_view, credores_list_view, diarias_list_view, reembolsos_list_view, jetons_list_view, auxilios_list_view, add_diaria_view, add_reembolso_view, add_jeton_view, add_auxilio_view, verbas_panel_view, agrupar_verbas_view, agrupar_impostos_view
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
]

