def user_in_group(user, group_name):
    """Verifica se um usuário (Django User) pertence a um grupo específico."""
    if user.is_superuser:
        return True
    if user.groups.filter(name=group_name).exists():
        return True
    return False
