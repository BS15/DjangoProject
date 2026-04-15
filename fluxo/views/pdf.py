"""PDF views do fluxo de pagamentos."""

from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.clickjacking import xframe_options_sameorigin

from commons.shared.pdf_response import gerar_resposta_pdf, montar_resposta_pdf
from fluxo.domain_models import Processo
from fluxo.pdf_generators import FLUXO_DOCUMENT_REGISTRY
from fluxo.services.processo_documentos import gerar_pdf_consolidado_processo


@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
@xframe_options_sameorigin
def visualizar_pdf_processo(request, processo_id):
    """Renderiza o PDF consolidado de documentos anexados ao processo.

    Gera visualização inline no navegador usando o consolidado retornado por
    `Processo.gerar_pdf_consolidado()`. Se o processo não tiver documentos PDF
    compatíveis, responde com `404` e mensagem textual.

    Parâmetros:
        request: Requisição HTTP autenticada.
        processo_id: ID do processo para geração do consolidado.

    Retorna:
        HttpResponse: Conteúdo `application/pdf` inline quando disponível.
    """
    processo = get_object_or_404(Processo, id=processo_id)

    pdf_buffer = gerar_pdf_consolidado_processo(processo)

    if pdf_buffer is None:
        return HttpResponse("Este processo ainda não possui documentos em PDF anexados.", status=404)

    nome_arquivo = f"Processo_{processo.n_nota_empenho or processo.id}.pdf"
    return montar_resposta_pdf(pdf_buffer, nome_arquivo, inline=True)


@permission_required("fluxo.pode_autorizar_pagamento", raise_exception=True)
@xframe_options_sameorigin
def gerar_autorizacao_pagamento_view(request, pk):
    """Gera e exibe o PDF de autorização de pagamento de um processo.

    Utiliza o motor de documentos (`gerar_documento_pdf`) com template lógico
    `autorizacao` e retorna o resultado para visualização inline.

    Parâmetros:
        request: Requisição HTTP autenticada com permissão de autorização.
        pk: ID do processo para o qual a autorização será gerada.

    Retorna:
        HttpResponse: PDF inline com nome de arquivo padronizado.
    """
    processo = get_object_or_404(Processo, pk=pk)
    nome_arquivo = f"Autorizacao_Pagamento_Proc_{processo.id}.pdf"
    return gerar_resposta_pdf(
        "autorizacao",
        processo,
        nome_arquivo,
        document_registry=FLUXO_DOCUMENT_REGISTRY,
        inline=True,
    )


@permission_required("fluxo.pode_auditar_conselho", raise_exception=True)
@xframe_options_sameorigin
def gerar_parecer_conselho_view(request, pk):
    """Gera e retorna o PDF de parecer do conselho para um processo."""
    processo = get_object_or_404(Processo, pk=pk)
    numero_reuniao = processo.reuniao_conselho.numero if hasattr(processo, 'reuniao_conselho') and processo.reuniao_conselho else None
    nome_arquivo = f"Parecer_Conselho_Fiscal_Proc_{processo.id}.pdf"
    return gerar_resposta_pdf(
        "conselho_fiscal",
        processo,
        nome_arquivo,
        document_registry=FLUXO_DOCUMENT_REGISTRY,
        inline=True,
        numero_reuniao=numero_reuniao,
    )


@permission_required("fluxo.pode_contabilizar", raise_exception=True)
@xframe_options_sameorigin
def gerar_termo_contabilizacao_view(request, pk):
    """Gera e exibe o PDF do Termo de Contabilização de um processo."""
    processo = get_object_or_404(Processo, pk=pk)
    nome_arquivo = f"Termo_Contabilizacao_Proc_{processo.id}.pdf"
    return gerar_resposta_pdf(
        "contabilizacao",
        processo,
        nome_arquivo,
        document_registry=FLUXO_DOCUMENT_REGISTRY,
        inline=True,
    )


@permission_required("fluxo.pode_auditar_conselho", raise_exception=True)
@xframe_options_sameorigin
def gerar_termo_auditoria_view(request, pk):
    """Gera e exibe o PDF do Termo de Auditoria de um processo."""
    processo = get_object_or_404(Processo, pk=pk)
    nome_arquivo = f"Termo_Auditoria_Proc_{processo.id}.pdf"
    return gerar_resposta_pdf(
        "auditoria",
        processo,
        nome_arquivo,
        document_registry=FLUXO_DOCUMENT_REGISTRY,
        inline=True,
    )


__all__ = [
    "visualizar_pdf_processo",
    "gerar_autorizacao_pagamento_view",
    "gerar_parecer_conselho_view",
    "gerar_termo_contabilizacao_view",
    "gerar_termo_auditoria_view",
]
