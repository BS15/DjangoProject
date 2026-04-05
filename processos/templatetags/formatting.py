"""Filtros de template para formatação padrão do backoffice."""

from django import template

from processos.utils import format_br_date, format_brl_amount, format_brl_currency

register = template.Library()


@register.filter(name="br_date")
def br_date(value, empty_value="-"):
    """Formata datas no padrão brasileiro para uso em templates."""
    return format_br_date(value, empty_value=empty_value)


@register.filter(name="br_currency")
def br_currency(value, empty_value="-"):
    """Formata valores monetários com símbolo de real."""
    return format_brl_currency(value, empty_value=empty_value)


@register.filter(name="br_amount")
def br_amount(value, empty_value="-"):
    """Formata valores no padrão brasileiro sem símbolo monetário."""
    return format_brl_amount(value, empty_value=empty_value)
