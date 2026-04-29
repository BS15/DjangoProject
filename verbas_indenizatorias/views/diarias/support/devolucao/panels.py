"""Paineis de devolucao de diarias (GET-only)."""

from decimal import Decimal

from django.contrib.auth.decorators import permission_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from commons.shared.query_tools import resolver_parametros_ordenacao
from verbas_indenizatorias.forms import DevolucaoDiariaForm
from verbas_indenizatorias.models import DevolucaoDiaria, Diaria


@require_GET
@permission_required("verbas_indenizatorias.pode_gerenciar_diarias", raise_exception=True)
def painel_devolucoes_diarias_view(request):
    """Lista devolucoes de diarias."""
    devolucoes = DevolucaoDiaria.objects.select_related("diaria__beneficiario", "registrado_por")

    beneficiario_q = (request.GET.get("beneficiario") or "").strip()
    if beneficiario_q:
        devolucoes = devolucoes.filter(diaria__beneficiario__nome__icontains=beneficiario_q)

    ordem, direcao, order_field = resolver_parametros_ordenacao(
        request,
        campos_permitidos={
            "diaria": "diaria__id",
            "beneficiario": "diaria__beneficiario__nome",
            "data_devolucao": "data_devolucao",
            "valor_devolvido": "valor_devolvido",
            "motivo": "motivo",
            "registrado_por": "registrado_por__username",
            "criado_em": "criado_em",
        },
        default_ordem="data_devolucao",
        default_direcao="desc",
    )
    devolucoes = devolucoes.order_by(order_field, "-id")

    total_devolvido = devolucoes.aggregate(total=Sum("valor_devolvido"))["total"] or Decimal("0")

    return render(
        request,
        "verbas/painel_devolucoes_diarias.html",
        {
            "devolucoes": devolucoes,
            "total_devolvido": total_devolvido,
            "filtro_beneficiario": beneficiario_q,
            "ordem": ordem,
            "direcao": direcao,
        },
    )


@require_GET
@permission_required("verbas_indenizatorias.pode_gerenciar_diarias", raise_exception=True)
def registrar_devolucao_diaria_view(request, pk):
    """Formulario para registrar devolucao de diaria."""
    diaria = get_object_or_404(Diaria.objects.select_related("beneficiario", "status"), pk=pk)
    form = DevolucaoDiariaForm()
    return render(
        request,
        "verbas/add_devolucao_diaria.html",
        {
            "form": form,
            "diaria": diaria,
        },
    )


__all__ = [
    "painel_devolucoes_diarias_view",
    "registrar_devolucao_diaria_view",
]
