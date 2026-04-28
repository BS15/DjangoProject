"""Panels (GET-only) do domínio de auxílios de representação."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render

from pagamentos.views.shared import render_filtered_list
from verbas_indenizatorias.forms import AuxilioForm
from verbas_indenizatorias.models import AuxilioRepresentacao
from verbas_indenizatorias.filters import AuxilioFilter


@permission_required("pagamentos.pode_visualizar_verbas", raise_exception=True)
def auxilios_list_view(request):
    """Renderiza lista paginada e filtrada de auxílios de representação."""
    queryset = AuxilioRepresentacao.objects.select_related("beneficiario", "status", "processo").order_by("-id")
    return render_filtered_list(
        request,
        queryset=queryset,
        filter_class=AuxilioFilter,
        template_name="verbas/auxilios_list.html",
        items_key="auxilios",
        filter_key="filter",
        sort_fields={
            "numero_sequencial": "numero_sequencial",
            "status": "status__status_choice",
            "beneficiario": "beneficiario__nome",
            "objetivo": "objetivo",
            "valor_total": "valor_total",
            "processo": "processo__id",
        },
        default_ordem="numero_sequencial",
        default_direcao="desc",
        tie_breaker="-id",
    )


@permission_required("pagamentos.pode_gerenciar_auxilios", raise_exception=True)
def add_auxilio_view(request):
    """Renderiza formulário de cadastro de novo auxílio."""
    return render(request, "verbas/add_auxilio.html", {"form": AuxilioForm()})


@permission_required("pagamentos.pode_gerenciar_auxilios", raise_exception=True)
def gerenciar_auxilio_view(request, pk):
    """Renderiza painel de detalhes e gestão de um auxílio específico."""
    auxilio = get_object_or_404(AuxilioRepresentacao.objects.select_related("beneficiario", "status", "processo"), id=pk)
    context = {
        "auxilio": auxilio,
        "pode_autorizar": request.user.has_perm("pagamentos.pode_gerenciar_auxilios"),
    }
    return render(request, "verbas/edit_auxilio.html", context)


@permission_required("pagamentos.pode_gerenciar_auxilios", raise_exception=True)
def cancelar_auxilio_spoke_view(request, pk):
    """Renderiza spoke de confirmação de cancelamento de auxílio."""
    auxilio = get_object_or_404(AuxilioRepresentacao.objects.select_related("beneficiario", "status", "processo"), id=pk)
    status_choice = (getattr(getattr(auxilio, "status", None), "status_choice", "") or "").upper()
    return render(request, "verbas/cancelar_auxilio_spoke.html", {
        "auxilio": auxilio,
        "entidade_paga": status_choice == "PAGA",
    })
