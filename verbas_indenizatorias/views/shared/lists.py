"""Helpers de listagem para telas de verbas indenizatorias."""

from fluxo.views.shared import render_filtered_list


def _render_lista_verba(request, model, filter_class, template_name):
    """Renderiza listagem filtrável padrão para módulos de verbas indenizatórias."""
    queryset = model.objects.select_related("beneficiario", "status", "processo").order_by("-id")
    return render_filtered_list(
        request,
        queryset=queryset,
        filter_class=filter_class,
        template_name=template_name,
        items_key="registros",
        filter_key="filter",
    )
