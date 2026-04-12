
"""Configuração do aplicativo de suprimentos de fundos para o sistema de backoffice público.

Este módulo define a configuração do app suprimentos, responsável pelo controle de suprimentos de fundos, despesas e prestação de contas.
"""

from django.apps import AppConfig


class SuprimentosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "suprimentos"
    verbose_name = "Suprimentos de Fundos"
