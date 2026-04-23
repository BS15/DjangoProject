"""Views de geração e visualização de PDFs do fluxo financeiro."""

from django.contrib.auth.decorators import permission_required
from django.http import Http404
from django.shortcuts import get_object_or_404

from commons.shared.pdf_response import gerar_documento_bytes, montar_resposta_pdf
from pagamentos.domain_models import Processo
from pagamentos.pdf_generators import FLUXO_DOCUMENT_REGISTRY
from pagamentos.services.processo_documentos import gerar_pdf_consolidado_processo


def _render_fluxo_pdf(doc_type, processo, nome_arquivo, **kwargs):
    """Gera PDF do registry de fluxo e devolve resposta inline."""
    pdf_bytes = gerar_documento_bytes(doc_type, processo, FLUXO_DOCUMENT_REGISTRY, **kwargs)
    return montar_resposta_pdf(pdf_bytes, nome_arquivo, inline=True)


@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def visualizar_pdf_processo(request, processo_id):
    """Exibe o PDF consolidado do processo quando houver documentos válidos."""
    processo = get_object_or_404(Processo, id=processo_id)
    pdf_buffer = gerar_pdf_consolidado_processo(processo)
    if pdf_buffer is None:
        raise Http404("Processo sem documentos válidos para gerar PDF.")
    return montar_resposta_pdf(pdf_buffer, f"processo_{processo.id}.pdf", inline=True)


@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def gerar_autorizacao_pagamento_view(request, pk):
    """Gera e exibe o Termo de Autorização de Pagamento do processo."""
    processo = get_object_or_404(Processo, id=pk)
    return _render_fluxo_pdf("autorizacao", processo, f"autorizacao_pagamento_{processo.id}.pdf")


@permission_required("pagamentos.pode_auditar_conselho", raise_exception=True)
def gerar_parecer_conselho_view(request, pk):
    """Gera e exibe o Parecer do Conselho Fiscal para o processo."""
    processo = get_object_or_404(Processo, id=pk)
    numero_reuniao = processo.reuniao_conselho.numero if processo.reuniao_conselho else None
    return _render_fluxo_pdf(
        "conselho_fiscal",
        processo,
        f"parecer_conselho_processo_{processo.id}.pdf",
        numero_reuniao=numero_reuniao,
    )


__all__ = [
    "visualizar_pdf_processo",
    "gerar_autorizacao_pagamento_view",
    "gerar_parecer_conselho_view",
]
