"""
processos/utils — Pacote modular de utilidades por domínio.

Este __init__.py re-exporta a API pública de sub-módulos para que código legado
fazendo `from processos.utils import <name>` continue funcionando.

✨ Novo padrão: imports específicos de domínio delegam para subpacotes:

  - shared/: utilidades cross-cutting (text formatting, PDF manipulation, reports)
  - verbas/: operações de verbas indenizatórias (diárias, import/sync)
  - fluxo/: operações do fluxo financeiro (fatura generation, etc)
  - Imports de topo: permissões, importação de dados cadastrais
"""

from django.core.files.storage import default_storage

# Re-exportar cada domínio de forma explícita para deixar claro sua origem

# Shared/cross-cutting utilities
from .shared import (
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
    mesclar_pdfs_em_memoria,
    merge_canvas_with_template,
    sort_pages,
    extract_siscac_data,
    interpretar_linha,
    processar_pdf_boleto,
    split_pdf_to_temp_pages,
    processar_pdf_comprovantes,
    parse_siscac_report,
    gerar_csv_relatorio,
)

# Verbas domain
from .verbas.diarias import (
    preview_diarias_lote,
    importar_diarias_lote,
    confirmar_diarias_lote,
    sync_diarias_siscac_csv,
)

# Fluxo domain
from .fluxo import gerar_faturas_do_mes

# Top-level imports (cadastro)
from .cadastros_import import importar_credores_csv, importar_contas_fixas_csv

# Note: Permission utilities moved to @permission_required decorator pattern
# See: .github/copilot-instructions.md#robust-security-rbac

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
    # utils_relatorios
    "gerar_csv_relatorio",
]
