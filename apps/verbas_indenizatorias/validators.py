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


def verificar_turnpike_diaria(diaria, status_anterior, novo_status_str):
    """Valida transições de status permitidas para diárias.

    A função retorna lista de erros; quando vazia, a transição está autorizada.
    """
    erros = []
    novo_status_upper = novo_status_str.upper()

    transicoes_validas = {
        '': ['SOLICITADA'],
        'SOLICITADA': ['APROVADA', 'REJEITADA'],
        'APROVADA': ['ENVIADA PARA PAGAMENTO', 'SOLICITADA'],
        'ENVIADA PARA PAGAMENTO': ['PAGA', 'APROVADA'],
        'PAGA': [],
    }

    if status_anterior:
        status_anterior_upper = status_anterior.upper()
        if status_anterior_upper in transicoes_validas and novo_status_upper not in transicoes_validas[status_anterior_upper]:
            permitidas = ', '.join(transicoes_validas.get(status_anterior_upper, [])) or 'nenhuma'
            erros.append(
                (
                    f"Transição inválida de '{status_anterior_upper}' para '{novo_status_upper}'. "
                    f"Transições permitidas: {permitidas}."
                )
            )

    return erros


__all__ = [
    "validar_vinculo_inicial_em_processo_selado",
    "verificar_turnpike_diaria",
]