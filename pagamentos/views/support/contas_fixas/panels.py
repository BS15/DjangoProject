"""Panels (GET-only) de contas fixas."""

from datetime import date

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from credores.models import ContaFixa, FaturaMensal, gerar_faturas_do_mes

from .forms import ContaFixaForm


def _mes_ano(request):
    hoje = date.today()
    try:
        mes = int(request.GET.get("mes", hoje.month))
    except (TypeError, ValueError):
        mes = hoje.month
    try:
        ano = int(request.GET.get("ano", hoje.year))
    except (TypeError, ValueError):
        ano = hoje.year
    mes = max(1, min(12, mes))
    ano = max(2000, min(2100, ano))
    return mes, ano


@require_GET
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def painel_contas_fixas_view(request):
    mes, ano = _mes_ano(request)
    gerar_faturas_do_mes(ano, mes)
    referencia = date(ano, mes, 1)
    faturas = (
        FaturaMensal.objects.filter(mes_referencia=referencia)
        .select_related("conta_fixa", "conta_fixa__credor", "processo_vinculado")
        .order_by("conta_fixa__credor__nome", "conta_fixa__referencia")
    )
    contas_fixas = ContaFixa.objects.select_related("credor").order_by("-ativa", "credor__nome", "referencia")
    return render(
        request,
        "contas/painel_contas_fixas.html",
        {"mes": mes, "ano": ano, "faturas": faturas, "contas_fixas": contas_fixas},
    )


@require_GET
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def add_conta_fixa_view(request):
    return render(request, "contas/add_conta_fixa.html", {"form": ContaFixaForm()})


@require_GET
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def edit_conta_fixa_view(request, pk):
    conta = get_object_or_404(ContaFixa, pk=pk)
    return render(
        request,
        "contas/edit_conta_fixa.html",
        {"conta": conta, "form": ContaFixaForm(instance=conta)},
    )


__all__ = ["painel_contas_fixas_view", "add_conta_fixa_view", "edit_conta_fixa_view"]
