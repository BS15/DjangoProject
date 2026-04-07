from django.urls import path

from processos.views import chaos as chaos_views
from processos.views import desenvolvedor as dev_views
from processos.views import teste_pdf

urlpatterns = [
    path('processo/<int:pk>/gerar-dummy-pdf/', dev_views.gerar_dummy_pdf_view, name='gerar_dummy_pdf'),
    path('dados-fake/', dev_views.gerar_dados_fake_view, name='gerar_dados_fake'),
    path('testes/pdfs/', teste_pdf.painel_teste_pdfs, name='painel_teste_pdfs'),
    path('testes/pdfs/gerar/<str:doc_type>/', teste_pdf.gerar_pdf_fake_view, name='gerar_pdf_fake'),
    path('ferramentas/chaos-testing/', chaos_views.chaos_testing_view, name='chaos_testing'),
]
