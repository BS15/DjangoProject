from django.urls import path

from desenvolvedor import views_desenvolvedor as dev_views

urlpatterns = [
    path('processo/<int:pk>/gerar-dummy-pdf/', dev_views.gerar_dummy_pdf_view, name='gerar_dummy_pdf'),
    path('dados-fake/', dev_views.gerar_dados_fake_view, name='gerar_dados_fake'),
    path('testes/pdfs/', dev_views.painel_teste_pdfs, name='painel_teste_pdfs'),
    path('testes/pdfs/gerar/<str:doc_type>/', dev_views.gerar_pdf_fake_view, name='gerar_pdf_fake'),
]
