from django.apps import AppConfig


class PagamentosConfig(AppConfig):
    """Configuração do aplicativo de pagamentos financeiros e documental."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "pagamentos"
    verbose_name = "Pagamentos Financeiros"
