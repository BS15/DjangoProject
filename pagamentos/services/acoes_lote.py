"""Serviços canônicos para ações em lote no fluxo de pagamentos."""

from django.db import transaction

from pagamentos.domain_models import Processo


def obter_processos_elegiveis_por_status(*, ids, status_origem_esperado):
    """Retorna processos elegíveis para transição considerando o status de origem."""
    return Processo.objects.filter(
        id__in=ids,
        status__opcao_status__iexact=status_origem_esperado,
    )


def atualizar_status_em_lote(ids, nome_status, usuario, queryset_base=None):
    """Avança status de processos em lote preservando regras de negócio e auditoria."""
    processos_qs = queryset_base if queryset_base is not None else Processo.objects.filter(id__in=ids)
    processos = processos_qs.select_related("status")

    total_atualizados = 0
    with transaction.atomic():
        for processo in processos:
            processo.avancar_status(nome_status, usuario=usuario)
            total_atualizados += 1

    return total_atualizados


__all__ = [
    "atualizar_status_em_lote",
    "obter_processos_elegiveis_por_status",
]
