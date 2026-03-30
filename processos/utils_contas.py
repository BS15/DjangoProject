import datetime
from .models import ContaFixa, FaturaMensal
from django.db.models import Q


def gerar_faturas_do_mes(ano, mes):
    data_ref = datetime.date(ano, mes, 1)
    contas_ativas = ContaFixa.objects.filter(
        ativa=True
    ).filter(
        Q(data_inicio__year__lt=ano) |
        Q(data_inicio__year=ano, data_inicio__month__lte=mes)
    )
    for conta in contas_ativas:
        FaturaMensal.objects.get_or_create(
            conta_fixa=conta,
            mes_referencia=data_ref
        )
