"""Paineis de devolucao (GET views)."""

from decimal import Decimal

from django.contrib.auth.decorators import permission_required
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from pagamentos.filters import DevolucaoFilter
from pagamentos.forms import DevolucaoForm
from pagamentos.domain_models import Devolucao, Processo
from pagamentos.views.shared import apply_filterset


@require_GET
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def painel_devolucoes_view(request: HttpRequest) -> HttpResponse:
    """Lista devolucoes com filtro e valor total agregado."""
    queryset = Devolucao.objects.select_related("processo", "processo__credor").order_by("-data_devolucao")
    meu_filtro = apply_filterset(request, DevolucaoFilter, queryset)
    total_valor = meu_filtro.qs.aggregate(total=Sum("valor_devolvido"))["total"] or Decimal("0")
    return render(
        request,
        "pagamentos/devolucoes_list.html",
        {
            "filter": meu_filtro,
            "devolucoes": meu_filtro.qs,
            "total_valor": total_valor,
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
