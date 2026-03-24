from django.core.exceptions import PermissionDenied
from functools import wraps


def user_in_group(user, group_name):
    """Verifica se um usuário (Django User) pertence a um grupo específico."""
    if user.is_superuser:
        return True
    if user.groups.filter(name=group_name).exists():
        return True
    return False


def group_required(*group_names):
    """Decorator for views that checks whether a user has a particular group, requiring login."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            if request.user.groups.filter(name__in=group_names).exists():
                return view_func(request, *args, **kwargs)
            raise PermissionDenied(f"Acesso negado. Requer um dos grupos: {', '.join(group_names)}")
        return _wrapped_view
    return decorator
