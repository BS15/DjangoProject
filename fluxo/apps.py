from django.apps import AppConfig


class FluxoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    """Configuração do aplicativo de fluxo financeiro e documental para o sistema de backoffice público.

    Este módulo define a configuração do app fluxo, responsável pelo controle de processos, documentos, pagamentos e integrações.
    """

    from django.apps import AppConfig

    class FluxoConfig(AppConfig):
        """Configuração do aplicativo de fluxo financeiro e documental."""
        name = "fluxo"
    verbose_name = "Fluxo Financeiro"
