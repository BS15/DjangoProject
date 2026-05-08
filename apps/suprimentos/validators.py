"""Validadores de domínio para suprimentos de fundos."""

from django.core.exceptions import ValidationError


def validar_regras_suprimento(cleaned_data):
    """Valida regras de negócio do formulário de suprimento de fundos.

    Retorna um dicionário no formato ``{campo: ValidationError}``.
    """
    errors = {}

    inicio_periodo = cleaned_data.get('inicio_periodo')
    fim_periodo = cleaned_data.get('fim_periodo')

    if inicio_periodo and fim_periodo and fim_periodo < inicio_periodo:
        errors['fim_periodo'] = ValidationError(
            "O período final não pode ser anterior ao período inicial."
        )

    return errors


__all__ = ["validar_regras_suprimento"]
