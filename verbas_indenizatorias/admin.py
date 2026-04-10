"""Configuração de admin de verbas indenizatórias: Diária, Reembolso, Jeton e Auxílio."""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    AuxilioRepresentacao,
    Diaria,
    DocumentoAuxilio,
    DocumentoDiaria,
    DocumentoJeton,
    DocumentoReembolso,
    Jeton,
    MeiosDeTransporte,
    ReembolsoCombustivel,
    StatusChoicesVerbasIndenizatorias,
    Tabela_Valores_Unitarios_Verbas_Indenizatorias,
    TiposDeVerbasIndenizatorias,
)


@admin.register(MeiosDeTransporte)
class MeiosDeTransporteAdmin(admin.ModelAdmin):
    """Admin de meios de transporte usados em diárias."""
    list_display = ('meio_de_transporte', 'is_active')
    search_fields = ('meio_de_transporte',)
    list_filter = ('is_active',)


admin.site.register(StatusChoicesVerbasIndenizatorias)
admin.site.register(TiposDeVerbasIndenizatorias)
admin.site.register(Tabela_Valores_Unitarios_Verbas_Indenizatorias)
admin.site.register(Diaria, SimpleHistoryAdmin)
admin.site.register(DocumentoDiaria, SimpleHistoryAdmin)
admin.site.register(ReembolsoCombustivel, SimpleHistoryAdmin)
admin.site.register(DocumentoReembolso, SimpleHistoryAdmin)
admin.site.register(Jeton, SimpleHistoryAdmin)
admin.site.register(DocumentoJeton, SimpleHistoryAdmin)
admin.site.register(AuxilioRepresentacao, SimpleHistoryAdmin)
admin.site.register(DocumentoAuxilio, SimpleHistoryAdmin)
