from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render

from fluxo.views.shared import render_filtered_list
from verbas_indenizatorias.forms import AuxilioForm
from verbas_indenizatorias.models import AuxilioRepresentacao
from verbas_indenizatorias.filters import AuxilioFilter


@permission_required("verbas_indenizatorias.pode_visualizar_verbas", raise_exception=True)
def auxilios_list_view(request):
    queryset = AuxilioRepresentacao.objects.select_related("beneficiario", "status", "processo").order_by("-id")
    return render_filtered_list(
        request,
        queryset=queryset,
        filter_class=AuxilioFilter,
        template_name="verbas/auxilios_list.html",
        items_key="auxilios",
        filter_key="filter",
    )


@permission_required("verbas_indenizatorias.pode_gerenciar_auxilios", raise_exception=True)
def add_auxilio_view(request):
    return render(request, "verbas/add_auxilio.html", {"form": AuxilioForm()})


@permission_required("verbas_indenizatorias.pode_gerenciar_auxilios", raise_exception=True)
def gerenciar_auxilio_view(request, pk):
    auxilio = get_object_or_404(AuxilioRepresentacao.objects.select_related("beneficiario", "status", "processo"), id=pk)
    context = {
        "auxilio": auxilio,
        "pode_autorizar": request.user.has_perm("verbas_indenizatorias.pode_gerenciar_auxilios"),
    }
    return render(request, "verbas/edit_auxilio.html", context)
