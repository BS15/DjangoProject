"""Paineis GET da etapa de contas a pagar."""

from django.contrib.auth.decorators import permission_required
from django.db.models import Exists, OuterRef
from django.shortcuts import render
from django.views.decorators.http import require_GET

from commons.shared.query_tools import obter_campo_ordenacao
from fiscal.models import RetencaoImposto
from pagamentos.domain_models import STATUS_PROCESSO_CONTAS_A_PAGAR, PendenciaProcessual, Processo
from pagamentos.views.helpers import (
    _aplicar_filtros_contas_a_pagar,
    _gerar_agrupamentos_contas_a_pagar,
)


STATUSES_CONTAS_A_PAGAR = list(STATUS_PROCESSO_CONTAS_A_PAGAR)


@require_GET
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def contas_a_pagar(request):
    """Renderiza a fila de contas a pagar com facetas, filtros e ordenacao."""
    processos_base = Processo.objects.filter(status__opcao_status__in=STATUSES_CONTAS_A_PAGAR)
    agrupamentos = _gerar_agrupamentos_contas_a_pagar(processos_base)

    data_selecionada = request.GET.get("data")
    forma_selecionada = request.GET.get("forma")
    status_selecionado = request.GET.get("status")
    conta_selecionada = request.GET.get("conta")
    ordem = request.GET.get("ordem", "id")
    direcao = request.GET.get("direcao", "asc")

    order_field = obter_campo_ordenacao(
        request,
        campos_permitidos={
            "id": "id",
            "data_pagamento": "data_pagamento",
            "credor": "credor__nome",
            "valor_liquido": "valor_liquido",
            "status": "status__opcao_status",
            "tipo_pagamento": "tipo_pagamento__tipo_pagamento",
        },
        default_ordem="id",
        default_direcao="asc",
    )

    qs_filtrada = _aplicar_filtros_contas_a_pagar(processos_base, request.GET)

    lista_processos = qs_filtrada.annotate(
        has_pendencias=Exists(PendenciaProcessual.objects.filter(processo=OuterRef("pk"))),
        has_retencoes=Exists(RetencaoImposto.objects.filter(nota_fiscal__processo=OuterRef("pk"))),
    ).order_by(order_field)

    context = {
        **agrupamentos,
        "lista_processos": lista_processos,
        "data_selecionada": data_selecionada,
        "forma_selecionada": forma_selecionada,
        "status_selecionado": status_selecionado,
        "conta_selecionada": conta_selecionada,
        "ordem": ordem,
        "direcao": direcao,
        "pode_interagir": True,
    }

    return render(request, "pagamentos/contas_a_pagar.html", context)


__all__ = ["STATUSES_CONTAS_A_PAGAR", "contas_a_pagar"]
