"""Helpers de parsing SISCAC da etapa de empenho."""

import logging
from decimal import Decimal

import pdfplumber

from commons.shared.pdf_tools import extract_text_between
from commons.shared.text_tools import parse_br_date, parse_brl_decimal


logger = logging.getLogger(__name__)


def sort_pages(pdf_file):
    """Classifica páginas SISCAC por tipo de conteúdo encontrado no texto."""
    pages_dict = {"empenho": [], "liquidacao": [], "pagamento": []}

    with pdfplumber.open(pdf_file) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if "Projetos/Atividades" in text:
                pages_dict["empenho"].append(i)
            if "Liquidação da Nota de Empenho" in text:
                pages_dict["liquidacao"].append(i)
            if "Serviço/Produto Adquirido" in text:
                pages_dict["pagamento"].append(i)
    return pages_dict


def extract_siscac_data(pdf_file):
    """Extrai dados essenciais de empenho de um PDF SISCAC."""
    pages_dict = sort_pages(pdf_file)
    data = {}

    with pdfplumber.open(pdf_file) as pdf:
        if pages_dict["empenho"]:
            text = pdf.pages[pages_dict["empenho"][0]].extract_text()

            data["n_nota_empenho"] = extract_text_between(text, "Número do Registro:", "Data:")
            raw_date = extract_text_between(text, "Data:", "Ano do Exercício:")

            data["data_empenho"] = parse_br_date(raw_date)
            data["ano_exercicio"] = extract_text_between(text, "Ano do Exercício:", "\n")
            data["credor"] = extract_text_between(text, "Credor:", "\n")
            total_bruto = Decimal("0")

            for p_idx in pages_dict["empenho"]:
                p_text = pdf.pages[p_idx].extract_text()
                val_str = extract_text_between(p_text, "Valor:", "\n")
                if val_str:
                    total_bruto += parse_brl_decimal(val_str, default=Decimal("0"))

            data["valor_bruto"] = float(total_bruto)

        obs_list = []
        for p_idx in pages_dict["liquidacao"]:
            text = pdf.pages[p_idx].extract_text()
            obs_list.append(extract_text_between(text, "LIQUIDAÇÃO - ", "Registro Contábil:"))

        data["observacao"] = obs_list

        total_liquido = Decimal("0")
        for p_idx in pages_dict["pagamento"]:
            text = pdf.pages[p_idx].extract_text()
            val_str = extract_text_between(text, "Valor Líquido:", "\n")
            if val_str:
                try:
                    total_liquido += parse_brl_decimal(val_str, default=Decimal("0"))
                except (TypeError, ValueError, ArithmeticError):
                    logger.warning("Falha ao converter valor liquido extraido do SISCAC")

        if total_liquido > 0:
            data["valor_liquido"] = float(total_liquido)

    return data


__all__ = ["sort_pages", "extract_siscac_data"]
