from django.contrib import admin
from django.contrib import admin
from .models import (
    CodigosImposto, StatusChoicesProcesso, TagChoices, FormasDePagamento,
    TiposDePagamento, TiposDeDocumento, Processo, DocumentoProcesso,
    NotaFiscal, RetencaoImposto, StatusChoicesVerbasIndenizatorias, Credor,
    ContasBancarias, TiposDeVerbasIndenizatorias,
    StatusChoicesPendencias, Grupos, CargosFuncoes,
    Tabela_Valores_Unitarios_Verbas_Indenizatorias, Tabela_Proponentes_Diarias,
    StatusChoicesRetencoes, TiposDePendencias, Pendencia, ComprovanteDePagamento
)
# ==========================================
# TABELAS DE PARAMETRIZAÇÃO (CONFIGURAÇÕES)
# ==========================================

@admin.register(CodigosImposto)
class CodigosImpostoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'is_active')
    search_fields = ('codigo',)
    list_filter = ('is_active',)

@admin.register(StatusChoicesProcesso)
class StatusChoicesAdmin(admin.ModelAdmin):
    list_display = ('status_choice', 'is_active')
    search_fields = ('status_choice',)
    list_filter = ('is_active',)

@admin.register(TagChoices)
class TagChoicesAdmin(admin.ModelAdmin):
    list_display = ('tag_choice', 'is_active')
    search_fields = ('tag_choice',)
    list_filter = ('is_active',)

@admin.register(FormasDePagamento)
class FormasDePagamentoAdmin(admin.ModelAdmin):
    list_display = ('forma_de_pagamento', 'is_active')
    search_fields = ('forma_de_pagamento',)
    list_filter = ('is_active',)

@admin.register(TiposDePagamento)
class TiposDePagamentoAdmin(admin.ModelAdmin):
    list_display = ('tipo_de_pagamento', 'is_active')
    search_fields = ('tipo_de_pagamento',)
    list_filter = ('is_active',)

@admin.register(TiposDeDocumento)
class TiposDeDocumentoAdmin(admin.ModelAdmin):
    list_display = ('tipo_de_documento', 'is_active')
    search_fields = ('tipo_de_documento',)
    list_filter = ('is_active',)

# ==========================================
# NÚCLEO DO SISTEMA (TRANSAÇÕES)
# ==========================================

@admin.register(Processo)
class ProcessoAdmin(admin.ModelAdmin):
    list_display = ('id', 'n_nota_empenho', 'credor', 'data_empenho', 'status')
    search_fields = ('n_nota_empenho', 'credor')
    list_filter = ('status', 'tipo_pagamento', 'forma_pagamento')

# Registros simples para as demais tabelas
admin.site.register(ContasBancarias)
admin.site.register(NotaFiscal)
admin.site.register(RetencaoImposto)
admin.site.register(DocumentoProcesso)
admin.site.register(StatusChoicesVerbasIndenizatorias)
admin.site.register(Credor)
admin.site.register(Grupos)
admin.site.register(CargosFuncoes)
admin.site.register(TiposDeVerbasIndenizatorias)
admin.site.register(StatusChoicesPendencias)
admin.site.register(Tabela_Valores_Unitarios_Verbas_Indenizatorias),
admin.site.register(Tabela_Proponentes_Diarias)
admin.site.register(StatusChoicesRetencoes)
admin.site.register(TiposDePendencias)
admin.site.register(Pendencia)


@admin.register(ComprovanteDePagamento)
class ComprovanteDePagamentoAdmin(admin.ModelAdmin):
    list_display = ('id', 'processo', 'credor_nome', 'valor_pago', 'tipo_de_pagamento', 'data_pagamento')
    search_fields = ('processo__n_nota_empenho', 'credor_nome')
    list_filter = ('tipo_de_pagamento',)