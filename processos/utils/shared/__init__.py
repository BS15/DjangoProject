"""Utilitários compartilhados entre domínios.

Consolidação de utilidades cross-cutting: relatórios, text manipulation,
PDF manipulation. Use imports diretos deste módulo ao invés de importar
de processos.utils.text_helpers, processos.utils.pdf_extractors, etc.
"""

# Re-exportar text formatting/parsing
from .text_tools import (
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

# Re-exportar PDF tools
from .pdf_tools import (
	split_pdf_to_temp_pages,
	sort_pages,
	extract_siscac_data,
	parse_siscac_report,
	interpretar_linha,
	processar_pdf_boleto,
	processar_pdf_comprovantes,
	mesclar_pdfs_em_memoria,
	merge_canvas_with_template,
)
from .errors import PdfMergeError

# Re-exportar relatórios
from .relatorios import gerar_csv_relatorio

__all__ = [
	# text_tools
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
	# pdf_tools
	"split_pdf_to_temp_pages",
	"sort_pages",
	"extract_siscac_data",
	"parse_siscac_report",
	"interpretar_linha",
	"processar_pdf_boleto",
	"processar_pdf_comprovantes",
	"mesclar_pdfs_em_memoria",
	"merge_canvas_with_template",
	"PdfMergeError",
	# relatorios
	"gerar_csv_relatorio",
]