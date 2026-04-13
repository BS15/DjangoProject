"""Utilitarios canonicos do dominio fluxo.

Consolida normalizacao textual, parsing monetario e processamento de PDF.
"""


"""Funções utilitárias para o domínio de fluxo financeiro e documental.

Este módulo implementa normalizações, extrações, formatações e utilidades para processamento de documentos, valores e datas.
"""

import io
import logging
import re
import uuid
from decimal import Decimal

import pdfplumber
import PyPDF2
from commons.shared.pdf_tools import extract_text_between
from commons.shared.text_tools import (
	_digits_only,
	decimals_equal_money,
	format_br_date,
	format_brl_amount,
	format_brl_currency,
	names_bidirectional_match,
	normalize_account,
	normalize_choice,
	normalize_document,
	normalize_name_for_match,
	normalize_text,
	parse_br_date,
	parse_brl_decimal,
)
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from pypdf import PdfReader, PdfWriter


logger = logging.getLogger(__name__)


class PdfMergeError(Exception):
	"""Erro ao mesclar arquivos PDF em memoria."""


def safe_split(line, keyword, index=1):
	"""Retorna o trecho após a palavra-chave em posição segura."""
	parts = line.split(keyword)
	if len(parts) > index:
		return parts[index].strip()
	return ""


def split_pdf_to_temp_pages(arquivo_pdf):
	"""Divide um PDF em páginas e salva cada página em arquivo temporário."""
	pdf = PdfReader(arquivo_pdf)
	paginas = []

	for numero_pagina in range(len(pdf.pages)):
		writer = PdfWriter()
		writer.add_page(pdf.pages[numero_pagina])

		buffer = io.BytesIO()
		writer.write(buffer)
		buffer.seek(0)

		nome_temp = f"temp_comprovante_{uuid.uuid4().hex[:8]}_pag{numero_pagina + 1}.pdf"
		caminho_salvo = default_storage.save(f"temp/{nome_temp}", ContentFile(buffer.read()))

		paginas.append({
			"temp_path": caminho_salvo,
			"url": default_storage.url(caminho_salvo),
			"pagina": numero_pagina + 1,
		})

	return paginas


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
	"""Extrai dados essenciais de empenho, liquidação e pagamento do SISCAC."""
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


def processar_pdf_boleto(pdf_file):
	"""Localiza linha digitável válida em PDF de boleto/arrecadação."""
	leitor = PyPDF2.PdfReader(pdf_file)
	texto = " ".join([pagina.extract_text() for pagina in leitor.pages if pagina.extract_text()])
	texto = re.sub(r"\s+", " ", texto)

	padrao = r"(?<!\d)(?:\d[\s\.\-]*){47,55}(?!\d)"
	candidatos = re.findall(padrao, texto)

	for candidato in candidatos:
		numeros = re.sub(r"\D", "", candidato)

		codigo_encontrado = None
		if len(numeros) == 48 and numeros.startswith("8"):
			codigo_encontrado = numeros
		elif len(numeros) == 47:
			codigo_encontrado = numeros
		elif 47 < len(numeros) <= 55:
			codigo_encontrado = numeros[-47:]

		if codigo_encontrado:
			return {
				"codigo_barras": codigo_encontrado,
				"valor": 0,
				"vencimento": "",
			}

	raise ValueError("Linha digitavel valida nao encontrada no PDF.")


def _extract_comprovante_fields(texto_flat):
	"""Extrai campos estruturados de um texto de comprovante bancário."""
	padrao_valor = re.compile(
		r"(?:VALOR TOTAL|VALOR DO DOCUMENTO|VALOR COBRADO|VALOR EM DINHEIRO|VALOR)\s*:?\s*(?:R\$\s*)?([\d.,]+)",
		re.IGNORECASE,
	)

	valor_float = 0.00
	for match_valor in padrao_valor.finditer(texto_flat):
		valor_str = match_valor.group(1).replace(".", "").replace(",", ".")
		try:
			valor_float = float(valor_str)
			break
		except ValueError:
			pass

	cpf_cnpj = re.findall(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2}", texto_flat)
	contas = re.findall(r"AGENCIA:\s*([\d-]+)\s*CONTA:\s*([\d.-]+[Xx]?)", texto_flat)

	data_pagamento = ""
	match_data = re.search(
		r"(?:DATA(?:\s*DO PAGAMENTO|\s*DA TRANSFERENCIA)?|DEBITO EM)\s*:?\s*(\d{2}/\d{2}/\d{4})",
		texto_flat,
		re.IGNORECASE,
	)
	if match_data:
		partes = match_data.group(1).split("/")
		if len(partes) == 3:
			data_pagamento = f"{partes[2]}-{partes[1]}-{partes[0]}"

	numero_comprovante = ""
	autenticacao_match = re.search(
		r"NR\.AUTENTICACAO\s*([A-Z0-9]\.[A-Z0-9]{3}\.[A-Z0-9]{3}\.[A-Z0-9]{3}\.[A-Z0-9]{3}\.[A-Z0-9]{3})",
		texto_flat,
		re.IGNORECASE,
	)
	if autenticacao_match:
		numero_comprovante = autenticacao_match.group(1)

	return {
		"valor_extraido": valor_float,
		"cpf_cnpj": cpf_cnpj,
		"contas": contas,
		"data_pagamento": data_pagamento,
		"numero_comprovante": numero_comprovante,
	}


def match_credor_por_cpf_cnpj(cpf_cnpj_list, cnpj_orgao_norm, Credor):
	"""Relaciona CPF/CNPJ extraído ao credor cadastrado, ignorando o órgão."""
	credor_encontrado = None
	cpf_cnpj_encontrados = []

	for cpf_cnpj in cpf_cnpj_list:
		cpf_cnpj_norm = normalize_document(cpf_cnpj)
		if cpf_cnpj_norm and cpf_cnpj_norm != cnpj_orgao_norm:
			credor = Credor.objects.filter(cpf_cnpj=cpf_cnpj).first()
			cpf_cnpj_encontrados.append({"cpf_cnpj": cpf_cnpj, "credor": credor})
			if credor and not credor_encontrado:
				credor_encontrado = credor

	return credor_encontrado, cpf_cnpj_encontrados


def _match_credor_por_contas(contas, agencia_orgao_norm, conta_orgao_norm, ContasBancarias):
	"""Relaciona agência/conta extraídas ao titular cadastrado, excluindo conta do órgão."""
	credor_encontrado = None
	contas_encontradas = []

	for agencia, conta in contas:
		agencia_norm, conta_norm = normalize_account(agencia, conta)
		if agencia_norm != agencia_orgao_norm or conta_norm != conta_orgao_norm:
			conta_db = ContasBancarias.objects.filter(agencia=agencia, conta=conta_norm).first()
			titular = conta_db.titular if conta_db else None
			contas_encontradas.append({"agencia": agencia, "conta": conta_norm, "credor": titular})
			if titular and not credor_encontrado:
				credor_encontrado = titular

	return credor_encontrado, contas_encontradas


def processar_pdf_comprovantes(pdf_file):
	"""Processa comprovantes em PDF e retorna dados extraídos por página."""
	from credores.models import Credor, ContasBancarias

	CNPJ_ORGAO = "82.894.098/0001-32"
	AGENCIA_ORGAO = "3582-3"
	CONTA_ORGAO_LIMPA = "7429-2"

	cnpj_orgao_norm = normalize_document(CNPJ_ORGAO)
	agencia_orgao_norm, conta_orgao_norm = normalize_account(AGENCIA_ORGAO, CONTA_ORGAO_LIMPA)

	paginas_temp = split_pdf_to_temp_pages(pdf_file)
	resultados = []

	for pagina_info in paginas_temp:
		with default_storage.open(pagina_info["temp_path"], "rb") as f:
			with pdfplumber.open(f) as pdf_leitor:
				texto = pdf_leitor.pages[0].extract_text() or ""

		texto_flat = re.sub(r"\s+", " ", texto)
		campos_extraidos = _extract_comprovante_fields(texto_flat)

		credor_por_cpf_cnpj, cpf_cnpj_encontrados = match_credor_por_cpf_cnpj(
			campos_extraidos["cpf_cnpj"],
			cnpj_orgao_norm,
			Credor,
		)
		credor_por_conta, contas_encontradas = _match_credor_por_contas(
			campos_extraidos["contas"],
			agencia_orgao_norm,
			conta_orgao_norm,
			ContasBancarias,
		)
		credor_encontrado = credor_por_cpf_cnpj or credor_por_conta

		resultados.append({
			**pagina_info,
			"credor_extraido": credor_encontrado.nome if credor_encontrado else None,
			"valor_extraido": campos_extraidos["valor_extraido"],
			"data_pagamento": campos_extraidos["data_pagamento"],
			"numero_comprovante": campos_extraidos["numero_comprovante"],
			"cpf_cnpj_encontrados": cpf_cnpj_encontrados,
			"contas_encontradas": contas_encontradas,
		})
	return resultados


def mesclar_pdfs_em_memoria(lista_arquivos):
	"""Mescla PDFs em memória e retorna buffer posicionado no início."""
	merger = PdfWriter()

	try:
		for arquivo in lista_arquivos:
			if arquivo:
				merger.append(arquivo)

		output_pdf = io.BytesIO()
		merger.write(output_pdf)
		merger.close()
		output_pdf.seek(0)
		return output_pdf
	except (PyPDF2.errors.PdfReadError, OSError, TypeError, ValueError) as exc:
		logger.exception("Erro na mesclagem de PDFs em memoria: %s", exc)
		raise PdfMergeError("Falha tecnica ao mesclar PDFs em memoria.") from exc


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
	"split_pdf_to_temp_pages",
	"sort_pages",
	"extract_siscac_data",
	"parse_siscac_report",
	"processar_pdf_boleto",
	"processar_pdf_comprovantes",
	"mesclar_pdfs_em_memoria",
	"PdfMergeError",
]
