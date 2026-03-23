import datetime
from .models import ContaFixa, FaturaMensal


def gerar_faturas_do_mes(ano, mes):
    data_ref = datetime.date(ano, mes, 1)
    contas_ativas = ContaFixa.objects.filter(ativa=True)
    for conta in contas_ativas:
        FaturaMensal.objects.get_or_create(
            conta_fixa=conta,
            mes_referencia=data_ref
        )
