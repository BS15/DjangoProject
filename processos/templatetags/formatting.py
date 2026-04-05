"""Template filters for Brazilian backoffice formatting."""

from django import template

from processos.utils import format_br_date, format_brl_amount, format_brl_currency

register = template.Library()


@register.filter(name="br_date")
def br_date(value, empty_value="-"):
    """Formats dates using the Brazilian pattern for templates."""
    return format_br_date(value, empty_value=empty_value)


@register.filter(name="br_currency")
def br_currency(value, empty_value="-"):
    """Formats values as Brazilian currency with the R$ symbol."""
    return format_brl_currency(value, empty_value=empty_value)


@register.filter(name="br_amount")
def br_amount(value, empty_value="-"):
    """Formats values as Brazilian amounts without the R$ symbol."""
    return format_brl_amount(value, empty_value=empty_value)
