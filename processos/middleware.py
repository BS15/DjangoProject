from django.conf import settings
from django.contrib.auth.views import redirect_to_login


class GlobalLoginRequiredMiddleware:
    """
    Middleware that enforces authentication for every request.

    Unauthenticated requests are redirected to settings.LOGIN_URL with the
    current path preserved as the ``next`` query parameter, UNLESS the request
    is already targeting the login page itself or a static/media asset (so the
    browser can still load CSS/JS and images on the login page).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            login_url = getattr(settings, 'LOGIN_URL', '/accounts/login/')
            static_url = getattr(settings, 'STATIC_URL', '/static/')
            media_url = getattr(settings, 'MEDIA_URL', '/media/')

            path = request.path_info
            # Allow the login page itself and all static/media assets through.
            if (
                not path.startswith(login_url)
                and not path.startswith(static_url)
                and not path.startswith(media_url)
            ):
                return redirect_to_login(request.get_full_path())

        return self.get_response(request)
