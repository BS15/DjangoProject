from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render

from pagamentos.views.shared import render_filtered_list
from verbas_indenizatorias.forms import JetonForm
from verbas_indenizatorias.models import Jeton
from verbas_indenizatorias.filters import JetonFilter


@permission_required("verbas_indenizatorias.pode_visualizar_verbas", raise_exception=True)
def jetons_list_view(request):
    queryset = Jeton.objects.select_related("beneficiario", "status", "processo").order_by("-id")
    return render_filtered_list(
        request,
        queryset=queryset,
        filter_class=JetonFilter,
        template_name="verbas/jetons_list.html",
        items_key="jetons",
        filter_key="filter",
    )


@permission_required("verbas_indenizatorias.pode_gerenciar_jetons", raise_exception=True)
def add_jeton_view(request):
    return render(request, "verbas/add_jeton.html", {"form": JetonForm()})


@permission_required("verbas_indenizatorias.pode_gerenciar_jetons", raise_exception=True)
def gerenciar_jeton_view(request, pk):
    jeton = get_object_or_404(Jeton.objects.select_related("beneficiario", "status", "processo"), id=pk)
    context = {
        "jeton": jeton,
        "reunioes_vinculadas": [],
        "pode_autorizar": request.user.has_perm("verbas_indenizatorias.pode_gerenciar_jetons"),
    }
    return render(request, "verbas/edit_jeton.html", context)


@permission_required("verbas_indenizatorias.pode_gerenciar_jetons", raise_exception=True)
def cancelar_jeton_spoke_view(request, pk):
    jeton = get_object_or_404(Jeton.objects.select_related("beneficiario", "status", "processo"), id=pk)
    status_choice = (getattr(getattr(jeton, "status", None), "status_choice", "") or "").upper()
    return render(request, "verbas/cancelar_jeton_spoke.html", {
        "jeton": jeton,
        "entidade_paga": status_choice == "PAGA",
    })
