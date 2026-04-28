"""Guardiões compartilhados de regras de processo."""


def is_processo_selado(processo):
    """Retorna True quando o processo está em estágio pós-pagamento selado."""
    if not processo or processo.em_contingencia or not processo.status:
        return False

    from pagamentos.domain_models.processos import STATUS_PROCESSO_PAGOS_E_POSTERIORES

    status_atual = (processo.status.opcao_status or "").upper()
    return status_atual in STATUS_PROCESSO_PAGOS_E_POSTERIORES


__all__ = ["is_processo_selado"]