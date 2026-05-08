
"""Configuração do aplicativo de credores para o sistema de backoffice público.

Este módulo define a configuração do app credores, responsável pelo cadastro e manutenção de credores, contas bancárias e contas fixas.
"""

from django.apps import AppConfig


class CadastrosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cadastros"
    verbose_name = "Cadastros"
