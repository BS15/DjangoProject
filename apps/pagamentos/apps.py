from django.apps import AppConfig


class PagamentosConfig(AppConfig):
    """Configuração do aplicativo de pagamentos financeiros e documental."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.pagamentos"
    verbose_name = "Pagamentos Financeiros"

    def ready(self):
        """Inicializa os signals da aplicação."""
        import apps.pagamentos.receivers  # noqa: F401
