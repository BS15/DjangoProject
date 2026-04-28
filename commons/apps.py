"""Configuração do app commons para registro no Django."""

from django.apps import AppConfig


class CommonsConfig(AppConfig):
    """Configuração do app de componentes compartilhados entre domínios."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'commons'
