
"""Configuração do aplicativo fiscal para o sistema de backoffice público.

Este módulo define a configuração do app fiscal, responsável por notas fiscais, retenções e comprovantes.
"""

from django.apps import AppConfig


class FiscalConfig(AppConfig):
    """Configuração do aplicativo fiscal."""
    name = "fiscal"
