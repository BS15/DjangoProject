"""Filtros de template built-in com nome de modulo unico para evitar colisao."""

from django import template

from commons.shared.text_tools import format_br_date, format_brl_amount, format_brl_currency, normalize_text

register = template.Library()


@register.filter(name="br_date")
def br_date(value, empty_value="-"):
    """Formata data no padrão brasileiro (DD/MM/AAAA)."""
    return format_br_date(value, empty_value=empty_value)


@register.filter(name="br_currency")
def br_currency(value, empty_value="-"):
    """Formata valor monetário no padrão R$."""
    return format_brl_currency(value, empty_value=empty_value)


@register.filter(name="br_amount")
def br_amount(value, empty_value="-"):
    """Formata valor numérico monetário sem símbolo de moeda."""
    return format_brl_amount(value, empty_value=empty_value)


@register.filter(name="normalize_text")
def normalize_text_filter(value):
    """Normaliza texto removendo acentos e convertendo para maiúsculas."""
    return normalize_text(value)
