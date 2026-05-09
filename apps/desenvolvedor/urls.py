"""URLs do aplicativo do desenvolvedor."""

from django.urls import path

from apps.desenvolvedor import views_desenvolvedor as dev_views

app_name = 'desenvolvedor'

urlpatterns = [
    path('dados-fake/', dev_views.gerar_dados_fake_view, name='gerar_dados_fake_list'),
    path('permissoes/', dev_views.painel_permissoes_dev_view, name='permissoes_dev_list'),
    path('api/permissoes/', dev_views.api_permissoes_dev_view, name='api_permissoes_dev'),
]