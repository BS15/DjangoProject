from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models.segments.auxiliary import (
    AssinaturaAutentique,
    RetencaoImposto,
    Pendencia,
    ReuniaoConselho,
    Devolucao,
    RegistroAcessoArquivo,
)
from .models.segments.parametrizations import (
    CodigosImposto,
    StatusChoicesProcesso,
    TagChoices,
    FormasDePagamento,
    TiposDePagamento,
    TiposDeDocumento,
    StatusChoicesVerbasIndenizatorias,
    TiposDeVerbasIndenizatorias,
    StatusChoicesPendencias,
    Tabela_Valores_Unitarios_Verbas_Indenizatorias,
    StatusChoicesRetencoes,
    TiposDePendencias,
    MeiosDeTransporte,
)
from .models.segments.core import (
    Processo,
    Diaria,
    ReembolsoCombustivel,
    Jeton,
    AuxilioRepresentacao,
    SuprimentoDeFundos,
)
from .models.segments.documents import (
    DocumentoProcesso,
    DocumentoFiscal,
    ComprovanteDePagamento,
    DocumentoDiaria,
    DocumentoReembolso,
    DocumentoJeton,
    DocumentoAuxilio,
    DocumentoSuprimentoDeFundos,
    DespesaSuprimento,
)
from .models.segments.cadastros import ContaFixa, Credor, ContasBancarias, FaturaMensal, CargosFuncoes, DadosContribuinte

@admin.register(CodigosImposto)
class CodigosImpostoAdmin(admin.ModelAdmin):
    """Admin de códigos de imposto com busca por código e filtro por ativo."""
    list_display = ('codigo', 'is_active')
    search_fields = ('codigo',)
    list_filter = ('is_active',)

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

@admin.register(MeiosDeTransporte)
class MeiosDeTransporteAdmin(admin.ModelAdmin):
    """Admin de meios de transporte usados em diárias."""
    list_display = ('meio_de_transporte', 'is_active')
    search_fields = ('meio_de_transporte',)
    list_filter = ('is_active',)

@admin.register(Processo)
class ProcessoAdmin(SimpleHistoryAdmin):
    """Admin principal do processo com trilha histórica."""
    list_display = ('id', 'n_nota_empenho', 'credor', 'data_empenho', 'status')
    search_fields = ('n_nota_empenho', 'credor')
    list_filter = ('status', 'tipo_pagamento', 'forma_pagamento')

admin.site.register(ContasBancarias, SimpleHistoryAdmin)
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
admin.site.register(CargosFuncoes, SimpleHistoryAdmin)
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
admin.site.register(ContaFixa, SimpleHistoryAdmin)
admin.site.register(FaturaMensal, SimpleHistoryAdmin)
admin.site.register(RegistroAcessoArquivo, SimpleHistoryAdmin)
admin.site.register(AssinaturaAutentique, SimpleHistoryAdmin)
admin.site.register(Devolucao, SimpleHistoryAdmin)


@admin.register(ComprovanteDePagamento)
class ComprovanteDePagamentoAdmin(SimpleHistoryAdmin):
    """Admin de comprovantes de pagamento com campos de conferência."""
    list_display = ('id', 'processo', 'numero_comprovante', 'credor_nome', 'valor_pago', 'data_pagamento')
    search_fields = ('processo__n_nota_empenho', 'credor_nome', 'numero_comprovante')


@admin.register(DadosContribuinte)
class DadosContribuinteAdmin(SimpleHistoryAdmin):
    """Admin de dados institucionais do contribuinte com registro único."""
    list_display = ('cnpj', 'razao_social', 'tipo_inscricao')

    def has_add_permission(self, request):
        """Impede criar novo registro quando já existe um contribuinte cadastrado."""
        if DadosContribuinte.objects.exists():
            return False
        return super().has_add_permission(request)

@admin.register(ReuniaoConselho)
class ReuniaoConselhoAdmin(admin.ModelAdmin):
    """Admin de reuniões do conselho fiscal."""
    list_display = ('numero', 'trimestre_referencia', 'data_reuniao', 'status')
    list_filter = ('status',)
    ordering = ('-numero',)
