"""Utilitários canônicos remanescentes do domínio fluxo."""

import re
from decimal import Decimal

import pdfplumber
from commons.shared.pdf_tools import extract_text_between


def safe_split(line, keyword, index=1):
	"""Retorna o trecho após a palavra-chave em posição segura."""
	parts = line.split(keyword)
	if len(parts) > index:
		return parts[index].strip()
	return ""


def parse_siscac_report(pdf_file):
	"""Lê relatório SISCAC e consolida lançamentos por número de pagamento."""
	pattern_payment = re.compile(r'^(20\d{2}PG\d{5})\s+(.*?)\s+(20\d{2}NE\d{5}).*?([\d.,]+)$')
	pattern_comprovante = re.compile(r'Nº do Comprovante:\s*([\d.-]+)')

	payments = {}
	current_comprovante = None

	with pdfplumber.open(pdf_file) as pdf:
		for page in pdf.pages:
			text = page.extract_text() or ''
			for line in text.splitlines():
				m_comp = pattern_comprovante.search(line)
				if m_comp:
					current_comprovante = m_comp.group(1).replace('.', '')

				m_pay = pattern_payment.match(line)
				if m_pay:
					pg = m_pay.group(1)
					credor = m_pay.group(2).strip()
					nota_empenho = m_pay.group(3)
					valor_str = m_pay.group(4)
					valor_decimal = Decimal(valor_str.replace('.', '').replace(',', '.'))

					if pg in payments:
						payments[pg]['valor_total'] += valor_decimal
					else:
						payments[pg] = {
							'siscac_pg': pg,
							'credor': credor,
							'nota_empenho': nota_empenho,
							'valor_total': valor_decimal,
							'comprovante': current_comprovante,
						}

	return list(payments.values())




__all__ = [
	"safe_split",
	"extract_text_between",
	"parse_siscac_report",
]
