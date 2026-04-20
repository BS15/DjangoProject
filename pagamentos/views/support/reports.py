"""Painéis de relatórios (GET views)."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from fiscal.models import RetencaoImposto
from pagamentos.domain_models import Processo
from pagamentos.filters import BaseStyledFilterSet, ProcessoFilter
from pagamentos.views.helpers.reports import gerar_csv_relatorio
from verbas_indenizatorias.models import Diaria


class DiariaReportFilter(BaseStyledFilterSet):
    class Meta:
        model = Diaria
        fields = []


class ImpostoReportFilter(BaseStyledFilterSet):
    class Meta:
        model = RetencaoImposto
        fields = []


TIPOS_RELATORIO = {
    "processos": (
        ProcessoFilter,
        Processo.objects.select_related("credor", "status").all().order_by("-id"),
    ),
    "diarias": (
        DiariaReportFilter,
        Diaria.objects.select_related("beneficiario", "proponente", "status").all().order_by("-id"),
    ),
    "impostos": (
        ImpostoReportFilter,
        RetencaoImposto.objects.select_related(
            "nota_fiscal",
            "nota_fiscal__processo",
            "codigo",
            "processo_pagamento",
        ).all().order_by("-id"),
    ),
}


@require_GET
@permission_required("pagamentos.acesso_backoffice", raise_exception=True)
def painel_relatorios_view(request):
    tipo = request.GET.get("tipo", "processos")
    if tipo not in TIPOS_RELATORIO:
        tipo = "processos"

    filter_class, queryset = TIPOS_RELATORIO[tipo]
    filtro = filter_class(request.GET, queryset=queryset)

    if request.GET.get("exportar") == "csv":
        return gerar_csv_relatorio(filtro.qs, tipo)

    return render(
        request,
        "relatorios/painel.html",
        {
            "tipo": tipo,
            "filtro": filtro,
        },
    )


@require_GET
@permission_required("pagamentos.acesso_backoffice", raise_exception=True)
def relatorio_documentos_gerados_view(request):
    return painel_relatorios_view(request)


__all__ = ["painel_relatorios_view", "relatorio_documentos_gerados_view"]
