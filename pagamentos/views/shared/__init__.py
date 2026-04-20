"""Shared view utilities for the pagamentos domain."""

from django.shortcuts import render


def apply_filterset(request, filter_class, queryset):
    """Instantiate a django-filters FilterSet bound to GET params."""
    return filter_class(request.GET, queryset=queryset)


def render_filtered_list(
    request,
    queryset,
    filter_class,
    template_name,
    items_key="items",
    filter_key="filter",
    extra_context=None,
):
    """Apply a filterset to a queryset and render a list template."""
    filterset = filter_class(request.GET, queryset=queryset)
    context = {
        filter_key: filterset,
        items_key: filterset.qs,
    }
    if extra_context:
        context.update(extra_context)
    return render(request, template_name, context)


__all__ = ["apply_filterset", "render_filtered_list"]
