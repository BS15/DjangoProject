def user_can_access_document(user, document):
    """
    Returns True if the user is allowed to access the given document object.
    Extend this logic according to business rules (ownership, department, etc).
    """
    # Superusers and auditors always have access
    if user.is_superuser or user.has_perm("pagamentos.pode_auditar_conselho"):
        return True
    # Owner-based access (using existing utility)
    from .access_utils import user_is_entity_owner
    if user_is_entity_owner(user, document):
        return True
    # Example: process-based access
    if hasattr(document, "processo") and hasattr(document.processo, "responsavel"):
        if document.processo.responsavel == user:
            return True
    # TODO: Add department/group-based rules as needed
    return False
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
