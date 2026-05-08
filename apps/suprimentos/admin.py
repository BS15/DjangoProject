"""Configuração de admin de suprimentos de fundos."""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import DespesaSuprimento, DocumentoSuprimentoDeFundos, SuprimentoDeFundos


admin.site.register(SuprimentoDeFundos, SimpleHistoryAdmin)
admin.site.register(DespesaSuprimento, SimpleHistoryAdmin)
admin.site.register(DocumentoSuprimentoDeFundos, SimpleHistoryAdmin)
