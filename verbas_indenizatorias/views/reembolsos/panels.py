"""Panels (GET-only) do domínio de reembolsos de combustível."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render

from pagamentos.views.shared import render_filtered_list
from verbas_indenizatorias.forms import ReembolsoForm
from verbas_indenizatorias.models import ReembolsoCombustivel
from verbas_indenizatorias.filters import ReembolsoFilter
from ..shared.registry import _get_tipos_documento_verbas


@permission_required("pagamentos.pode_visualizar_verbas", raise_exception=True)
def reembolsos_list_view(request):
    """Renderiza lista paginada e filtrada de reembolsos de combustível."""
    queryset = ReembolsoCombustivel.objects.select_related("beneficiario", "status", "processo").order_by("-id")
    return render_filtered_list(
        request,
        queryset=queryset,
        filter_class=ReembolsoFilter,
        template_name="verbas/reembolsos_list.html",
        items_key="reembolsos",
        filter_key="filter",
        sort_fields={
            "numero_sequencial": "numero_sequencial",
            "status": "status__status_choice",
            "beneficiario": "beneficiario__nome",
            "data_saida": "data_saida",
            "valor_total": "valor_total",
            "processo": "processo__id",
        },
        default_ordem="numero_sequencial",
        default_direcao="desc",
        tie_breaker="-id",
    )


@permission_required("pagamentos.pode_gerenciar_reembolsos", raise_exception=True)
def add_reembolso_view(request):
    """Renderiza formulário de cadastro de novo reembolso."""
    return render(request, "verbas/add_reembolso.html", {"form": ReembolsoForm()})


@permission_required("pagamentos.pode_gerenciar_reembolsos", raise_exception=True)
def gerenciar_reembolso_view(request, pk):
    """Renderiza painel de detalhes e gestão de um reembolso específico."""
    reembolso = get_object_or_404(ReembolsoCombustivel.objects.select_related("beneficiario", "status", "processo"), id=pk)
    comprovantes = reembolso.documentos.select_related("tipo").all()
    context = {
        "reembolso": reembolso,
        "comprovantes": comprovantes,
        "tipos_documento": _get_tipos_documento_verbas(),
        "pode_autorizar": request.user.has_perm("pagamentos.pode_gerenciar_reembolsos"),
    }
    return render(request, "verbas/edit_reembolso.html", context)


@permission_required("pagamentos.pode_gerenciar_reembolsos", raise_exception=True)
def cancelar_reembolso_spoke_view(request, pk):
    """Renderiza spoke de confirmação de cancelamento de reembolso."""
    reembolso = get_object_or_404(ReembolsoCombustivel.objects.select_related("beneficiario", "status", "processo"), id=pk)
    status_choice = (getattr(getattr(reembolso, "status", None), "status_choice", "") or "").upper()
    return render(request, "verbas/cancelar_reembolso_spoke.html", {
        "reembolso": reembolso,
        "entidade_paga": status_choice == "PAGA",
    })
