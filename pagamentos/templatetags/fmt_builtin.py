"""Filtros de template built-in com nome de modulo unico para evitar colisao."""

from django import template

from commons.shared.text_tools import format_br_date, format_brl_amount, format_brl_currency, normalize_text

register = template.Library()
register.filter("br_date", format_br_date)
register.filter("br_currency", format_brl_currency)
register.filter("br_amount", format_brl_amount)
register.filter("normalize_text", normalize_text)
