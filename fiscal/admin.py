"""Configuração de admin fiscal: notas fiscais, retenções de impostos e comprovantes."""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    CodigosImposto,
    DocumentoFiscal,
    RetencaoImposto,
    StatusChoicesRetencoes,
)


@admin.register(CodigosImposto)
class CodigosImpostoAdmin(admin.ModelAdmin):
    """Admin de códigos de imposto com busca por código e filtro por ativo."""
    list_display = ('codigo', 'is_active')
    search_fields = ('codigo',)
    list_filter = ('is_active',)


admin.site.register(DocumentoFiscal, SimpleHistoryAdmin)
admin.site.register(RetencaoImposto, SimpleHistoryAdmin)
admin.site.register(StatusChoicesRetencoes)
