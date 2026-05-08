from django.conf import settings
from django.contrib.auth.views import redirect_to_login


class GlobalLoginRequiredMiddleware:
    """Force authentication for every request except login/static URLs."""

    def __init__(self, get_response):
        """Inicializa o middleware com a função de resposta subsequente."""
        self.get_response = get_response

    def __call__(self, request):
        """Redireciona para login quando o usuário não está autenticado."""
        if not request.user.is_authenticated:
            login_url = getattr(settings, "LOGIN_URL", "/accounts/login/")
            static_url = getattr(settings, "STATIC_URL", "/static/")

            path = request.path_info
            if not path.startswith(login_url) and not path.startswith(static_url):
                return redirect_to_login(request.get_full_path())

        return self.get_response(request)
