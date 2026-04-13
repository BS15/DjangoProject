from django.apps import AppConfig


class FluxoConfig(AppConfig):
    """Configuração do aplicativo de fluxo financeiro e documental."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "fluxo"
    verbose_name = "Fluxo Financeiro"
