"""Utilitários de View compartilhados no sistema."""

from django.shortcuts import render

from commons.shared.query_tools import resolver_parametros_ordenacao


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
        ordem, direcao, order_field = resolver_parametros_ordenacao(
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

from commons.shared.text_tools import parse_brl_decimal

def extrair_dados_devolucao_do_post(request) -> dict | None:
    """Extrai campos de devolução do POST/FILES do request."""
    valor_raw = (request.POST.get("valor_devolvido") or "").strip()
    if not valor_raw:
        return None
    return {
        "valor_devolvido": parse_brl_decimal(valor_raw),
        "data_devolucao": (request.POST.get("data_devolucao") or "").strip() or None,
        "motivo": (request.POST.get("motivo") or "").strip() or None,
        "comprovante": request.FILES.get("comprovante") or None,
    }