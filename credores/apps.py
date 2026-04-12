
"""Configuração do aplicativo de credores para o sistema de backoffice público.

Este módulo define a configuração do app credores, responsável pelo cadastro e manutenção de credores, contas bancárias e contas fixas.
"""

from django.apps import AppConfig


class CredoresConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "credores"
    verbose_name = "Cadastro de Credores"
