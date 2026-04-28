"""Validadores de domínio para verbas indenizatórias."""

from django.core.exceptions import ValidationError as DjangoValidationError

from commons.shared.processo_guards import is_processo_selado


def validar_vinculo_inicial_em_processo_selado(processo, entidade_label):
    """Bloqueia criação de verba já vinculada a processo pós-pagamento."""
    if is_processo_selado(processo):
        raise DjangoValidationError(
            {
                "processo": (
                    f"Cadastro bloqueado: não é permitido vincular {entidade_label} "
                    "a processo em estágio pós-pagamento. "
                    "Use fluxo de contingência aprovado para ajustes."
                )
            }
        )


__all__ = ["validar_vinculo_inicial_em_processo_selado"]