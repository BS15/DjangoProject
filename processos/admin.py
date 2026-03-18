from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import (
    CodigosImposto, StatusChoicesProcesso, TagChoices, FormasDePagamento,
    TiposDePagamento, TiposDeDocumento, Processo, DocumentoProcesso,
    DocumentoFiscal, RetencaoImposto, StatusChoicesVerbasIndenizatorias, Credor,
    ContasBancarias, TiposDeVerbasIndenizatorias,
    StatusChoicesPendencias, Grupos, CargosFuncoes,
    Tabela_Valores_Unitarios_Verbas_Indenizatorias,
    StatusChoicesRetencoes, TiposDePendencias, Pendencia, ComprovanteDePagamento,
    DocumentoDiaria, DocumentoReembolso, DocumentoJeton, DocumentoAuxilio,
    DocumentoSuprimentoDeFundos, MeiosDeTransporte,
    Diaria, ReembolsoCombustivel, Jeton, AuxilioRepresentacao,
    SuprimentoDeFundos, DespesaSuprimento, DadosContribuinte,
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

@admin.register(MeiosDeTransporte)
class MeiosDeTransporteAdmin(admin.ModelAdmin):
    list_display = ('meio_de_transporte', 'is_active')
    search_fields = ('meio_de_transporte',)
    list_filter = ('is_active',)

# ==========================================
# NÚCLEO DO SISTEMA (TRANSAÇÕES)
# ==========================================

@admin.register(Processo)
class ProcessoAdmin(SimpleHistoryAdmin):
    list_display = ('id', 'n_nota_empenho', 'credor', 'data_empenho', 'status')
    search_fields = ('n_nota_empenho', 'credor')
    list_filter = ('status', 'tipo_pagamento', 'forma_pagamento')

# Registros simples para as demais tabelas
admin.site.register(ContasBancarias)
admin.site.register(DocumentoFiscal, SimpleHistoryAdmin)
admin.site.register(RetencaoImposto, SimpleHistoryAdmin)
admin.site.register(DocumentoProcesso, SimpleHistoryAdmin)
admin.site.register(DocumentoDiaria, SimpleHistoryAdmin)
admin.site.register(DocumentoReembolso, SimpleHistoryAdmin)
admin.site.register(DocumentoJeton, SimpleHistoryAdmin)
admin.site.register(DocumentoAuxilio, SimpleHistoryAdmin)
admin.site.register(DocumentoSuprimentoDeFundos, SimpleHistoryAdmin)
admin.site.register(StatusChoicesVerbasIndenizatorias)
admin.site.register(Credor, SimpleHistoryAdmin)
admin.site.register(Grupos)
admin.site.register(CargosFuncoes)
admin.site.register(TiposDeVerbasIndenizatorias)
admin.site.register(StatusChoicesPendencias)
admin.site.register(Tabela_Valores_Unitarios_Verbas_Indenizatorias)
admin.site.register(StatusChoicesRetencoes)
admin.site.register(TiposDePendencias)
admin.site.register(Pendencia, SimpleHistoryAdmin)
admin.site.register(Diaria, SimpleHistoryAdmin)
admin.site.register(ReembolsoCombustivel, SimpleHistoryAdmin)
admin.site.register(Jeton, SimpleHistoryAdmin)
admin.site.register(AuxilioRepresentacao, SimpleHistoryAdmin)
admin.site.register(SuprimentoDeFundos, SimpleHistoryAdmin)
admin.site.register(DespesaSuprimento, SimpleHistoryAdmin)


@admin.register(ComprovanteDePagamento)
class ComprovanteDePagamentoAdmin(SimpleHistoryAdmin):
    list_display = ('id', 'processo', 'numero_comprovante', 'credor_nome', 'valor_pago', 'data_pagamento')
    search_fields = ('processo__n_nota_empenho', 'credor_nome', 'numero_comprovante')


@admin.register(DadosContribuinte)
class DadosContribuinteAdmin(admin.ModelAdmin):
    list_display = ('cnpj', 'razao_social', 'tipo_inscricao')

    def has_add_permission(self, request):
        if DadosContribuinte.objects.exists():
            return False
        return super().has_add_permission(request)