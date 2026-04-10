"""Configuração de admin fiscal: notas fiscais, retenções de impostos e comprovantes."""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    CodigosImposto,
    ComprovanteDePagamento,
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


@admin.register(ComprovanteDePagamento)
class ComprovanteDePagamentoAdmin(SimpleHistoryAdmin):
    """Admin de comprovantes de pagamento com campos de conferência."""
    list_display = ('id', 'processo', 'numero_comprovante', 'credor_nome', 'valor_pago', 'data_pagamento')
    search_fields = ('processo__documentos_orcamentarios__numero_nota_empenho', 'credor_nome', 'numero_comprovante')


admin.site.register(DocumentoFiscal, SimpleHistoryAdmin)
admin.site.register(RetencaoImposto, SimpleHistoryAdmin)
admin.site.register(StatusChoicesRetencoes)
