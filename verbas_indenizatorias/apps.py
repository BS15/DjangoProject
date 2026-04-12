from django.apps import AppConfig


class VerbasIndenizatoriasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    """Configuração do aplicativo de verbas indenizatórias."""
    name = "verbas_indenizatorias"
    
"""Configuração do aplicativo de verbas indenizatórias para o sistema de backoffice público.

Este módulo define a configuração do app verbas indenizatórias, responsável pelo controle de diárias, reembolsos, jetons e auxílios.
"""
    verbose_name = "Verbas Indenizatorias"
