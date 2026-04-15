"""Utilitários compartilhados para geração e resposta HTTP de PDFs."""

from commons.shared.pdf_tools import gerar_documento_pdf
from django.http import HttpResponse


def gerar_documento_bytes(doc_type, obj, document_registry, **kwargs):
    """Gera bytes de PDF com um registry explícito do domínio chamador."""
    return gerar_documento_pdf(doc_type, obj, document_registry, **kwargs)


def montar_resposta_pdf(pdf_bytes, nome_arquivo, inline=True):
    """Monta `HttpResponse` de PDF com disposition inline/attachment."""
    disposition = "inline" if inline else "attachment"
    if hasattr(pdf_bytes, "read"):
        try:
            pdf_bytes.seek(0)
        except (AttributeError, OSError):
            pass
        content = pdf_bytes.read()
    else:
        content = pdf_bytes
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'{disposition}; filename="{nome_arquivo}"'
    return response


def gerar_resposta_pdf(doc_type, obj, nome_arquivo, document_registry, inline=True, **kwargs):
    """Gera bytes e devolve resposta HTTP de PDF com registry explícito."""
    pdf_bytes = gerar_documento_bytes(doc_type, obj, document_registry, **kwargs)
    return montar_resposta_pdf(pdf_bytes, nome_arquivo, inline=inline)


__all__ = ["gerar_documento_bytes", "montar_resposta_pdf", "gerar_resposta_pdf"]
