"""Context processors globais do projeto."""

import datetime

from apps.cadastros.models import FaturaMensal


def navbar_alerts(request):
    """Retorna total de faturas pendentes com vencimento nos proximos 5 dias."""
    # Dependência intencional de app de domínio: o agregador de alertas da navbar
    # consome dados de módulos de negócio (hoje cadastros/FaturaMensal). Futuras
    # expansões (verbas, suprimentos, etc.) devem ser adicionadas aqui.
    if not request.user.is_authenticated:
        return {}

    hoje = datetime.date.today()
    limite_alerta = hoje + datetime.timedelta(days=5)

    faturas_pendentes = FaturaMensal.objects.filter(
        mes_referencia__lte=hoje.replace(day=1)
    ).select_related("conta_fixa", "processo_vinculado")

    contas_vencendo = 0
    for fatura in faturas_pendentes:
        if fatura.status in ["PENDENTE", "EM ANDAMENTO"] and fatura.data_vencimento_exata <= limite_alerta:
            contas_vencendo += 1

    return {"total_contas_alerta": contas_vencendo}
