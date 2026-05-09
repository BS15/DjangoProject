"""Filtros base isolados e compartilhados do sistema.

Este módulo define componentes utilitários para django-filters, garantindo
estilos consistentes e padrões para listagens (ex: Bootstrap widgets).
"""

import django_filters
from django.db import models


def date_range_filter(*, label, method=None):
    """Cria um filtro de intervalo de datas com widget HTML nativo."""
    return django_filters.DateFromToRangeFilter(
        label=label,
        method=method,
        widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}),
    )


def month_filter(field_name, *, label='Mês'):
    """Cria um filtro numérico para mês a partir de um campo de data."""
    return django_filters.NumberFilter(field_name=field_name, lookup_expr='month', label=label)


def year_filter(field_name, *, label='Ano'):
    """Cria um filtro numérico para ano a partir de um campo de data."""
    return django_filters.NumberFilter(field_name=field_name, lookup_expr='year', label=label)


def icontains_filter(*, field_name=None, label=None):
    """Cria um filtro textual padronizado com busca parcial case-insensitive."""
    return django_filters.CharFilter(field_name=field_name, lookup_expr='icontains', label=label)


def exact_text_filter(*, field_name=None, label=None):
    """Cria um filtro textual padronizado com comparação exata."""
    return django_filters.CharFilter(field_name=field_name, lookup_expr='exact', label=label)


def boolean_filter(*, label):
    """Cria um filtro booleano com widget textual padronizado do django-filters."""
    return django_filters.BooleanFilter(label=label, widget=django_filters.widgets.BooleanWidget())


class BaseStyledFilterSet(django_filters.FilterSet):
    """Base de filtros com estilo Bootstrap consistente."""

    UNSUPPORTED_TEXTUAL_FIELDS = (models.FileField, models.JSONField)

    @classmethod
    def filter_for_field(cls, field, field_name, lookup_expr=None):
        """Converte tipos não suportados, como `FileField`, em filtros textuais."""
        if isinstance(field, cls.UNSUPPORTED_TEXTUAL_FIELDS):
            return django_filters.CharFilter(
                field_name=field_name,
                lookup_expr=lookup_expr or 'icontains',
            )
        try:
            return super().filter_for_field(field, field_name, lookup_expr)
        except AssertionError:
            return django_filters.CharFilter(
                field_name=field_name,
                lookup_expr='icontains',
            )

    def __init__(self, *args, **kwargs):
        """Aplica classes Bootstrap em todos os campos do formulário de filtro."""
        super().__init__(*args, **kwargs)
        for field in self.form.fields.values():
            field.widget.attrs.update({'class': 'form-control form-control-sm'})