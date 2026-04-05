"""View-layer helpers shared across multiple list/filter screens."""

from django.shortcuts import render


def apply_filterset(request, filter_class, queryset):
    """Instancia um FilterSet padronizado com os parâmetros GET atuais."""
    return filter_class(request.GET, queryset=queryset)


def render_filtered_list(
    request,
    *,
    queryset,
    filter_class,
    template_name,
    items_key,
    filter_key="meu_filtro",
    extra_context=None,
):
    """Renderiza telas de listagem baseadas em queryset + FilterSet."""
    filterset = apply_filterset(request, filter_class, queryset)
    context = {
        filter_key: filterset,
        items_key: filterset.qs,
    }
    if extra_context:
        context.update(extra_context)
    return render(request, template_name, context)
