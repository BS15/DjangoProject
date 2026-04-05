"""
processos/utils — Modular utility package.

This __init__.py re-exports the public API of all sub-modules so that
existing callers (views, models, tests) that do
    from processos.utils import <name>
continue to work without any changes.
"""

from django.core.files.storage import default_storage

from .text_helpers import (
    normalize_document,
    normalize_account,
    normalize_text,
    normalize_name_for_match,
    names_bidirectional_match,
    decimals_equal_money,
    normalize_choice,
    format_br_date,
    format_brl_currency,
    format_brl_amount,
    parse_brl_decimal,
    safe_split,
    parse_br_date,
    extract_text_between,
)

from .pdf_multipurpose_tools import (
    mesclar_pdfs_em_memoria,
    merge_canvas_with_template,
)

from .pdf_extractors import (
    sort_pages,
    extract_siscac_data,
    interpretar_linha,
    processar_pdf_boleto,
    split_pdf_to_temp_pages,
    processar_pdf_comprovantes,
    parse_siscac_report,
)

from .siscac_diarias_sync import sync_diarias_siscac_csv

from .csv_imports import (
    preview_diarias_lote,
    importar_diarias_lote,
    confirmar_diarias_lote,
)

from .utils_contas import gerar_faturas_do_mes
from .utils_import import importar_credores_csv, importar_contas_fixas_csv
from .utils_permissoes import user_in_group, group_required
from .utils_relatorios import gerar_csv_relatorio

__all__ = [
    # compatibility exports
    "default_storage",
    # text_helpers
    "normalize_document",
    "normalize_account",
    "normalize_text",
    "normalize_name_for_match",
    "names_bidirectional_match",
    "decimals_equal_money",
    "normalize_choice",
    "format_br_date",
    "format_brl_currency",
    "format_brl_amount",
    "parse_brl_decimal",
    "safe_split",
    "parse_br_date",
    "extract_text_between",
    # pdf_generation
    "mesclar_pdfs_em_memoria",
    "merge_canvas_with_template",
    # pdf_extraction
    "sort_pages",
    "extract_siscac_data",
    "interpretar_linha",
    "processar_pdf_boleto",
    "split_pdf_to_temp_pages",
    "processar_pdf_comprovantes",
    "parse_siscac_report",
    # csv_imports
    "sync_diarias_siscac_csv",
    "preview_diarias_lote",
    "importar_diarias_lote",
    "confirmar_diarias_lote",
    # utils_contas
    "gerar_faturas_do_mes",
    # utils_import
    "importar_credores_csv",
    "importar_contas_fixas_csv",
    # utils_permissoes
    "user_in_group",
    "group_required",
    # utils_relatorios
    "gerar_csv_relatorio",
]
