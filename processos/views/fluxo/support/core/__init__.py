"""Core views e utilities transversais do modulo support."""

from typing import Any

from django.contrib.auth.decorators import permission_required
from django.db.models import OuterRef, Subquery
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .....models import DocumentoOrcamentario, Processo
from ...helpers import _obter_campo_ordenacao
from ....shared import apply_filterset
from .....filters import ProcessoFilter


__all__ = [
    "_obter_campo_ordenacao",
    "aplicar_aprovacao_contingencia",
    "determinar_requisitos_contingencia",
    "normalizar_dados_propostos_contingencia",
    "proximo_status_contingencia",
    "sincronizar_flag_contingencia_processo",
    "home_page",
    "process_detail_view",
]


# Re-export helpers da fluxo
from ...helpers import (
    aplicar_aprovacao_contingencia,
    determinar_requisitos_contingencia,
    normalizar_dados_propostos_contingencia,
    proximo_status_contingencia,
    sincronizar_flag_contingencia_processo,
)


@require_GET
def home_page(request: HttpRequest) -> HttpResponse:
    """Lista processos no painel inicial com filtro e ordenacao segura."""
    order_field = _obter_campo_ordenacao(
        request,
        campos_permitidos={
            "id": "id",
            "credor": "credor__nome",
            "data_empenho": "data_empenho_ordem",
            "status": "status__status_choice",
            "tipo_pagamento": "tipo_pagamento__tipo_de_pagamento",
            "valor_liquido": "valor_liquido",
        },
    )

    subquery_empenho = DocumentoOrcamentario.objects.filter(processo_id=OuterRef("pk")).order_by("-data_empenho", "-id")
    processos_base = Processo.objects.annotate(
        data_empenho_ordem=Subquery(subquery_empenho.values("data_empenho")[:1])
    ).all().order_by(order_field)
    meu_filtro = apply_filterset(request, ProcessoFilter, processos_base)

    context: dict[str, Any] = {
        "lista_processos": meu_filtro.qs,
        "meu_filtro": meu_filtro,
        "ordem": request.GET.get("ordem", "id"),
        "direcao": request.GET.get("direcao", "desc"),
    }
    return render(request, "home.html", context)


@require_GET
@permission_required("processos.acesso_backoffice", raise_exception=True)
def process_detail_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Detalhe de um processo individual."""
    processo: Any = get_object_or_404(Processo, pk=pk)
    documentos = processo.documentos.all()
    status_permite_devolucao = {
        "PAGO - A CONTABILIZAR",
        "CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL",
        "APROVADO - PENDENTE ARQUIVAMENTO",
        "ARQUIVADO",
    }
    pode_registrar_devolucao = processo.status and processo.status.status_choice in status_permite_devolucao
    return render(
        request,
        "fluxo/process_detail.html",
        {
            "processo": processo,
            "documentos": documentos,
            "pode_registrar_devolucao": pode_registrar_devolucao,
        },
    )
