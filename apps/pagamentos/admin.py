"""Configuração de admin do fluxo de pagamento: Processo, Pendência, Devolução e catálogos."""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    AssinaturaEletronica,
    ContingenciaProcessual,
    DevolucaoProcessual,
    BoletoBancario,
    DocumentoOrcamentarioProcessual,
    DocumentoProcesso,
    FormasPagamento,
    PendenciaProcessual,
    Processo,
    RegistroAcessoArquivoProcessual,
    ReuniaoConselhoFiscal,
    StatusOpcoesPendencia,
    StatusOpcoesProcesso,
    OpcoesEtiqueta,
    TiposDocumento,
    TiposPagamento,
    TiposPendencia,
)


@admin.register(StatusOpcoesProcesso)
class StatusChoicesAdmin(admin.ModelAdmin):
    """Admin de status do processo para manutenção de catálogo."""
    list_display = ('opcao_status', 'ativo')
    search_fields = ('opcao_status',)
    list_filter = ('ativo',)


@admin.register(OpcoesEtiqueta)
class TagChoicesAdmin(admin.ModelAdmin):
    """Admin de etiquetas de classificação de processo."""
    list_display = ('opcao_etiqueta', 'ativo')
    search_fields = ('opcao_etiqueta',)
    list_filter = ('ativo',)


@admin.register(FormasPagamento)
class FormasDePagamentoAdmin(admin.ModelAdmin):
    """Admin de formas de pagamento."""
    list_display = ('forma_pagamento', 'ativo')
    search_fields = ('forma_pagamento',)
    list_filter = ('ativo',)


@admin.register(TiposPagamento)
class TiposDePagamentoAdmin(admin.ModelAdmin):
    """Admin de tipos de pagamento."""
    list_display = ('tipo_pagamento', 'ativo')
    search_fields = ('tipo_pagamento',)
    list_filter = ('ativo',)


@admin.register(TiposDocumento)
class TiposDeDocumentoAdmin(admin.ModelAdmin):
    """Admin de tipos de documento."""
    list_display = ('tipo_documento', 'ativo')
    search_fields = ('tipo_documento',)
    list_filter = ('ativo',)


@admin.register(Processo)
class ProcessoAdmin(SimpleHistoryAdmin):
    """Admin principal do processo com trilha histórica."""
    list_display = ('id', 'n_nota_empenho', 'credor', 'data_empenho', 'status')
    search_fields = ('documentos_orcamentarios__numero_nota_empenho', 'credor__nome')
    list_filter = ('status', 'tipo_pagamento', 'forma_pagamento')


@admin.register(ReuniaoConselhoFiscal)
class ReuniaoConselhoAdmin(admin.ModelAdmin):
    """Admin de reuniões do conselho fiscal."""
    list_display = ('numero', 'trimestre_referencia', 'data_reuniao', 'status')
    list_filter = ('status',)
    ordering = ('-numero',)


admin.site.register(BoletoBancario, SimpleHistoryAdmin)
admin.site.register(DocumentoProcesso, SimpleHistoryAdmin)
admin.site.register(DocumentoOrcamentarioProcessual, SimpleHistoryAdmin)
admin.site.register(PendenciaProcessual, SimpleHistoryAdmin)
admin.site.register(StatusOpcoesPendencia)
admin.site.register(TiposPendencia)
admin.site.register(DevolucaoProcessual, SimpleHistoryAdmin)
admin.site.register(AssinaturaEletronica, SimpleHistoryAdmin)
admin.site.register(RegistroAcessoArquivoProcessual, SimpleHistoryAdmin)
admin.site.register(ContingenciaProcessual)
