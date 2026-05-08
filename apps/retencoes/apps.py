
"""Configuração do aplicativo fiscal para o sistema de backoffice público.

Este módulo define a configuração do app fiscal, responsável por notas fiscais, retenções e comprovantes.
"""

from django.apps import AppConfig


class RetencoesConfig(AppConfig):
    """Configuração do aplicativo de retenções."""
    name = "apps.retencoes"
