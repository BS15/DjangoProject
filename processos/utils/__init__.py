"""
processos/utils — Modular utility package.

This __init__.py re-exports the public API of all sub-modules so that
existing callers (views, models, tests) that do
    from processos.utils import <name>
continue to work without any changes.
"""

from .text_helpers import (
    normalize_document,
    normalize_account,
    normalize_name_for_match,
    names_bidirectional_match,
    decimals_equal_money,
    safe_split,
    parse_br_date,
    extract_text_between,
)

from .pdf_generation import (
    mesclar_pdfs_em_memoria,
    merge_canvas_with_template,
    gerar_termo_auditoria,
)

from .pdf_extraction import (
    sort_pages,
    extract_siscac_data,
    interpretar_linha,
    processar_pdf_boleto,
    split_pdf_to_temp_pages,
    processar_pdf_comprovantes,
    parse_siscac_report,
    sync_siscac_payments,
)

from .csv_imports import (
    sync_diarias_siscac_csv,
    preview_diarias_lote,
    importar_diarias_lote,
    confirmar_diarias_lote,
)

__all__ = [
    # text_helpers
    "normalize_document",
    "normalize_account",
    "normalize_name_for_match",
    "names_bidirectional_match",
    "decimals_equal_money",
    "safe_split",
    "parse_br_date",
    "extract_text_between",
    # pdf_generation
    "mesclar_pdfs_em_memoria",
    "merge_canvas_with_template",
    "gerar_termo_auditoria",
    # pdf_extraction
    "sort_pages",
    "extract_siscac_data",
    "interpretar_linha",
    "processar_pdf_boleto",
    "split_pdf_to_temp_pages",
    "processar_pdf_comprovantes",
    "parse_siscac_report",
    "sync_siscac_payments",
    # csv_imports
    "sync_diarias_siscac_csv",
    "preview_diarias_lote",
    "importar_diarias_lote",
    "confirmar_diarias_lote",
]
