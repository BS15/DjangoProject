"""Shared view utilities for the pagamentos domain."""

from django.shortcuts import render

from pagamentos.views.helpers import _resolver_parametros_ordenacao


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
    sort_fields=None,
    default_ordem="id",
    default_direcao="desc",
    tie_breaker="-id",
):
    """Apply a filterset to a queryset and render a list template."""
    filterset = filter_class(request.GET, queryset=queryset)

    items = filterset.qs
    sort_context = {}
    if sort_fields:
        ordem, direcao, order_field = _resolver_parametros_ordenacao(
            request,
            campos_permitidos=sort_fields,
            default_ordem=default_ordem,
            default_direcao=default_direcao,
        )
        if tie_breaker:
            items = items.order_by(order_field, tie_breaker)
        else:
            items = items.order_by(order_field)
        sort_context = {
            "ordem": ordem,
            "direcao": direcao,
        }

    context = {
        filter_key: filterset,
        items_key: items,
        **sort_context,
    }
    if extra_context:
        context.update(extra_context)
    return render(request, template_name, context)


__all__ = ["apply_filterset", "render_filtered_list"]
