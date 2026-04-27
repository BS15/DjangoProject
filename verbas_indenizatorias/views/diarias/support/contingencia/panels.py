"""Paineis de contingencia de diarias (GET-only)."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from pagamentos.views.helpers import _resolver_parametros_ordenacao
from verbas_indenizatorias.forms import ContingenciaDiariaForm
from verbas_indenizatorias.models import ContingenciaDiaria, Diaria


@require_GET
@permission_required("pagamentos.pode_gerenciar_diarias", raise_exception=True)
def painel_contingencias_diarias_view(request):
    """Lista contingencias de diarias com filtro basico por status."""
    contingencias = ContingenciaDiaria.objects.select_related(
        "diaria__beneficiario", "solicitante", "aprovado_por"
    )

    status_filtro = (request.GET.get("status") or "").strip().upper()
    if status_filtro in {"PENDENTE_SUPERVISOR", "APROVADA", "REJEITADA"}:
        contingencias = contingencias.filter(status=status_filtro)

    ordem, direcao, order_field = _resolver_parametros_ordenacao(
        request,
        campos_permitidos={
            "id": "id",
            "diaria": "diaria__id",
            "beneficiario": "diaria__beneficiario__nome",
            "campo_corrigido": "campo_corrigido",
            "solicitante": "solicitante__username",
            "status": "status",
            "criado_em": "criado_em",
        },
        default_ordem="criado_em",
        default_direcao="desc",
    )
    contingencias = contingencias.order_by(order_field, "-id")

    return render(
        request,
        "verbas/painel_contingencias_diarias.html",
        {
            "contingencias": contingencias,
            "filtro_status": status_filtro,
            "ordem": ordem,
            "direcao": direcao,
        },
    )


@require_GET
@permission_required("pagamentos.pode_gerenciar_diarias", raise_exception=True)
def add_contingencia_diaria_view(request, pk):
    """Formulario de abertura de contingencia para diaria."""
    diaria = get_object_or_404(Diaria.objects.select_related("beneficiario", "status"), pk=pk)
    form = ContingenciaDiariaForm()
    return render(
        request,
        "verbas/add_contingencia_diaria.html",
        {
            "form": form,
            "diaria": diaria,
        },
    )


__all__ = [
    "painel_contingencias_diarias_view",
    "add_contingencia_diaria_view",
]
