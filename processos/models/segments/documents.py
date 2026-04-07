"""Modelos e utilitarios de documentos."""

from ._fluxo_models import DocumentoBase, DocumentoDePagamento, DocumentoProcesso, DocumentoOrcamentario, caminho_documento
from ._fiscal_models import DocumentoFiscal, ComprovanteDePagamento, caminho_comprovante
from ._verbas_models import DocumentoDiaria, DocumentoReembolso, DocumentoJeton, DocumentoAuxilio
from ._suprimentos_models import DocumentoSuprimentoDeFundos, DespesaSuprimento

__all__ = [
    "DocumentoBase",
    "DocumentoDePagamento",
    "DocumentoProcesso",
    "DocumentoOrcamentario",
    "DocumentoFiscal",
    "ComprovanteDePagamento",
    "DocumentoDiaria",
    "DocumentoReembolso",
    "DocumentoJeton",
    "DocumentoAuxilio",
    "DocumentoSuprimentoDeFundos",
    "DespesaSuprimento",
    "caminho_documento",
    "caminho_comprovante",
]
