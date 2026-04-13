"""Funções utilitárias de acesso e ownership compartilhadas entre apps."""

def user_is_entity_owner(user, entidade):
    """Retorna True quando o usuário é o dono funcional da entidade."""
    if user is None or entidade is None:
        return False

    campos_relacao = (
        "proponente",
        "beneficiario",
        "credor",
        "suprido",
        "solicitante",
        "criador",
    )

    user_email = (getattr(user, "email", None) or "").strip().lower()
    for campo in campos_relacao:
        relacionado = getattr(entidade, campo, None)
        if not relacionado:
            continue

        if relacionado == user:
            return True

        relacionado_email = (getattr(relacionado, "email", None) or "").strip().lower()
        if user_email and relacionado_email and relacionado_email == user_email:
            return True

    return False
