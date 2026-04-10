"""Views de leitura para contas fixas."""

import datetime

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render

from credores.models import ContaFixa, FaturaMensal
from fluxo.utils import gerar_faturas_do_mes


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def painel_contas_fixas_view(request):
    """Exibe painel mensal de contas fixas e faturas geradas automaticamente."""
    hoje = datetime.date.today()
    mes = int(request.GET.get("mes", hoje.month))
    ano = int(request.GET.get("ano", hoje.year))

    gerar_faturas_do_mes(ano, mes)

    data_ref = datetime.date(ano, mes, 1)
    faturas = (
        FaturaMensal.objects.filter(mes_referencia=data_ref)
        .select_related("conta_fixa__credor", "processo_vinculado")
        .order_by("conta_fixa__dia_vencimento")
    )

    context = {
        "faturas": faturas,
        "mes": mes,
        "ano": ano,
        "contas_fixas": ContaFixa.objects.select_related("credor").order_by("credor__nome", "referencia"),
    }
    return render(request, "contas/painel_contas_fixas.html", context)