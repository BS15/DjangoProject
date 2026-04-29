"""Paineis de devolucao (GET views)."""

from decimal import Decimal

from django.contrib.auth.decorators import permission_required
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from commons.shared.query_tools import resolver_parametros_ordenacao
from pagamentos.filters import DevolucaoFilter
from pagamentos.forms import DevolucaoForm
from pagamentos.domain_models import Devolucao, Processo
from pagamentos.views.shared import apply_filterset


@require_GET
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def painel_devolucoes_view(request: HttpRequest) -> HttpResponse:
    """Lista devolucoes com filtro e valor total agregado."""
    queryset = Devolucao.objects.select_related("processo", "processo__credor")
    meu_filtro = apply_filterset(request, DevolucaoFilter, queryset)
    ordem, direcao, order_field = resolver_parametros_ordenacao(
        request,
        campos_permitidos={
            "processo": "processo__id",
            "credor": "processo__credor__nome",
            "data_devolucao": "data_devolucao",
            "valor_devolvido": "valor_devolvido",
            "motivo": "motivo",
            "criado_em": "criado_em",
        },
        default_ordem="data_devolucao",
        default_direcao="desc",
    )
    devolucoes = meu_filtro.qs.order_by(order_field, "-id")
    total_valor = devolucoes.aggregate(total=Sum("valor_devolvido"))["total"] or Decimal("0")
    return render(
        request,
        "pagamentos/devolucoes_list.html",
        {
            "filter": meu_filtro,
            "devolucoes": devolucoes,
            "total_valor": total_valor,
            "ordem": ordem,
            "direcao": direcao,
        },
    )


@require_GET
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def registrar_devolucao_view(request: HttpRequest, processo_id: int) -> HttpResponse:
    """Renderiza formulario para registrar devolucao vinculada ao processo."""
    processo = get_object_or_404(Processo, id=processo_id)
    form = DevolucaoForm()

    return render(request, "pagamentos/add_devolucao.html", {"form": form, "processo": processo})


__all__ = [
    "painel_devolucoes_view",
    "registrar_devolucao_view",
]
