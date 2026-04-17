"""Configuração de admin do fluxo de pagamento: Processo, Pendência, Devolução e catálogos."""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    AssinaturaAutentique,
    Contingencia,
    Devolucao,
    Boleto_Bancario,
    DocumentoOrcamentario,
    DocumentoProcesso,
    FormasDePagamento,
    Pendencia,
    Processo,
    RegistroAcessoArquivo,
    ReuniaoConselho,
    StatusChoicesPendencias,
    StatusChoicesProcesso,
    TagChoices,
    TiposDeDocumento,
    TiposDePagamento,
    TiposDePendencias,
)


@admin.register(StatusChoicesProcesso)
class StatusChoicesAdmin(admin.ModelAdmin):
    """Admin de status do processo para manutenção de catálogo."""
    list_display = ('status_choice', 'is_active')
    search_fields = ('status_choice',)
    list_filter = ('is_active',)


@admin.register(TagChoices)
class TagChoicesAdmin(admin.ModelAdmin):
    """Admin de etiquetas de classificação de processo."""
    list_display = ('tag_choice', 'is_active')
    search_fields = ('tag_choice',)
    list_filter = ('is_active',)


@admin.register(FormasDePagamento)
class FormasDePagamentoAdmin(admin.ModelAdmin):
    """Admin de formas de pagamento."""
    list_display = ('forma_de_pagamento', 'is_active')
    search_fields = ('forma_de_pagamento',)
    list_filter = ('is_active',)


@admin.register(TiposDePagamento)
class TiposDePagamentoAdmin(admin.ModelAdmin):
    """Admin de tipos de pagamento."""
    list_display = ('tipo_de_pagamento', 'is_active')
    search_fields = ('tipo_de_pagamento',)
    list_filter = ('is_active',)


@admin.register(TiposDeDocumento)
class TiposDeDocumentoAdmin(admin.ModelAdmin):
    """Admin de tipos de documento."""
    list_display = ('tipo_de_documento', 'is_active')
    search_fields = ('tipo_de_documento',)
    list_filter = ('is_active',)


@admin.register(Processo)
class ProcessoAdmin(SimpleHistoryAdmin):
    """Admin principal do processo com trilha histórica."""
    list_display = ('id', 'n_nota_empenho', 'credor', 'data_empenho', 'status')
    search_fields = ('documentos_orcamentarios__numero_nota_empenho', 'credor__nome')
    list_filter = ('status', 'tipo_pagamento', 'forma_pagamento')


@admin.register(ReuniaoConselho)
class ReuniaoConselhoAdmin(admin.ModelAdmin):
    """Admin de reuniões do conselho fiscal."""
    list_display = ('numero', 'trimestre_referencia', 'data_reuniao', 'status')
    list_filter = ('status',)
    ordering = ('-numero',)


admin.site.register(Boleto_Bancario, SimpleHistoryAdmin)
admin.site.register(DocumentoProcesso, SimpleHistoryAdmin)
admin.site.register(DocumentoOrcamentario, SimpleHistoryAdmin)
admin.site.register(Pendencia, SimpleHistoryAdmin)
admin.site.register(StatusChoicesPendencias)
admin.site.register(TiposDePendencias)
admin.site.register(Devolucao, SimpleHistoryAdmin)
admin.site.register(AssinaturaAutentique, SimpleHistoryAdmin)
admin.site.register(RegistroAcessoArquivo, SimpleHistoryAdmin)
admin.site.register(Contingencia)
