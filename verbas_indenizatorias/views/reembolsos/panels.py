from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render

from fluxo.views.shared import render_filtered_list
from verbas_indenizatorias.forms import ReembolsoForm
from verbas_indenizatorias.models import ReembolsoCombustivel
from verbas_indenizatorias.filters import ReembolsoFilter
from ..shared.registry import _get_tipos_documento_verbas


@permission_required("verbas_indenizatorias.pode_visualizar_verbas", raise_exception=True)
def reembolsos_list_view(request):
    queryset = ReembolsoCombustivel.objects.select_related("beneficiario", "status", "processo").order_by("-id")
    return render_filtered_list(
        request,
        queryset=queryset,
        filter_class=ReembolsoFilter,
        template_name="verbas/reembolsos_list.html",
        items_key="reembolsos",
        filter_key="filter",
    )


@permission_required("verbas_indenizatorias.pode_gerenciar_reembolsos", raise_exception=True)
def add_reembolso_view(request):
    return render(request, "verbas/add_reembolso.html", {"form": ReembolsoForm()})


@permission_required("verbas_indenizatorias.pode_gerenciar_reembolsos", raise_exception=True)
def gerenciar_reembolso_view(request, pk):
    reembolso = get_object_or_404(ReembolsoCombustivel.objects.select_related("beneficiario", "status", "processo"), id=pk)
    comprovantes = reembolso.documentos.select_related("tipo").all()
    context = {
        "reembolso": reembolso,
        "comprovantes": comprovantes,
        "tipos_documento": _get_tipos_documento_verbas(),
        "pode_autorizar": request.user.has_perm("verbas_indenizatorias.pode_gerenciar_reembolsos"),
    }
    return render(request, "verbas/edit_reembolso.html", context)
