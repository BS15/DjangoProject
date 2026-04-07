"""Paineis GET da etapa de empenho."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .....filters import AEmpenharFilter
from .....models import Processo
from ....shared import apply_filterset
from ...helpers import _obter_campo_ordenacao


@require_GET
@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def a_empenhar_view(request):
    """Exibe a fila filtravel/ordenavel dos processos pendentes de empenho."""
    order_field = _obter_campo_ordenacao(
        request,
        campos_permitidos={
            "id": "id",
            "credor": "credor__nome",
            "valor_liquido": "valor_liquido",
            "data_vencimento": "data_vencimento",
            "tipo_pagamento": "tipo_pagamento__tipo_de_pagamento",
        },
        default_ordem="data_vencimento",
        default_direcao="asc",
    )

    processos_base = Processo.objects.filter(status__status_choice__iexact="A EMPENHAR").select_related(
        "credor", "status", "tipo_pagamento"
    )
    meu_filtro = apply_filterset(request, AEmpenharFilter, processos_base)

    context = {
        "processos": meu_filtro.qs.order_by(order_field, "-id"),
        "meu_filtro": meu_filtro,
        "ordem": request.GET.get("ordem", "data_vencimento"),
        "direcao": request.GET.get("direcao", "asc"),
        "pode_interagir": True,
    }
    return render(request, "fluxo/a_empenhar.html", context)


__all__ = ["a_empenhar_view"]
