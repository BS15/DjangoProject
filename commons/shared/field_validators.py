"""Validadores compartilhados para campos de domínio."""

import re

from django.core.exceptions import ValidationError


def validar_cpf_cnpj(value):
    """Valida formato básico de CPF/CNPJ (apenas dígitos e separadores)."""
    if not value:
        return

    clean = re.sub(r"\D", "", value)
    if not re.match(r"^(\d{11}|\d{14})$", clean):
        raise ValidationError(
            "CPF deve ter 11 dígitos e CNPJ deve ter 14 dígitos.",
            code="invalid_cpf_cnpj",
        )

    if len(clean) == 11 and clean == clean[0] * 11:
        raise ValidationError("CPF inválido (dígitos repetidos).", code="invalid_cpf")

    if len(clean) == 14 and clean == clean[0] * 14:
        raise ValidationError("CNPJ inválido (dígitos repetidos).", code="invalid_cnpj")


__all__ = ["validar_cpf_cnpj"]