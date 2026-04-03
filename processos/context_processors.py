"""Context processors globais usados nos templates do sistema."""

import datetime

from processos.models.cadastros import FaturaMensal


def alertas_contas_fixas(request):
    """Calcula quantidade de faturas pendentes com vencimento próximo para o cabeçalho."""
    if not request.user.is_authenticated:
        return {}

    hoje = datetime.date.today()
    limite_alerta = hoje + datetime.timedelta(days=5)

    faturas_pendentes = FaturaMensal.objects.filter(
        mes_referencia__lte=hoje.replace(day=1)
    ).select_related('conta_fixa', 'processo_vinculado')

    contas_vencendo = 0
    for fatura in faturas_pendentes:
        if fatura.status in ['PENDENTE', 'EM ANDAMENTO']:
            if fatura.data_vencimento_exata <= limite_alerta:
                contas_vencendo += 1

    return {'total_contas_alerta': contas_vencendo}
