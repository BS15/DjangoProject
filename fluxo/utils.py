"""Utilitarios canonicos do dominio fluxo.

Consolida normalizacao textual, parsing monetario e processamento de PDF.
"""

import io
import logging
import re
import unicodedata
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

import pdfplumber
import PyPDF2
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from pypdf import PdfReader, PdfWriter


logger = logging.getLogger(__name__)


class PdfMergeError(Exception):
	"""Erro ao mesclar arquivos PDF em memoria."""


def _digits_only(value):
	return re.sub(r"\D", "", value or "")


def normalize_text(value, *, collapse_spaces=True):
	if not value:
		return ""

	normalized = unicodedata.normalize("NFD", value.upper())
	no_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
	if not collapse_spaces:
		return no_accents.strip()
	return re.sub(r"\s+", " ", no_accents).strip()


def normalize_document(value):
	return _digits_only(value)


def normalize_account(agencia, conta):
	agencia_norm = (agencia or "").strip().replace(" ", "")
	conta_norm = (conta or "").strip().replace(" ", "").replace(".", "")
	return agencia_norm.upper(), conta_norm.upper()


def normalize_name_for_match(value):
	return normalize_text(value)


def names_bidirectional_match(left, right):
	left_norm = normalize_name_for_match(left)
	right_norm = normalize_name_for_match(right)
	if not left_norm or not right_norm:
		return False
	return left_norm in right_norm or right_norm in left_norm


def decimals_equal_money(left, right):
	if left is None or right is None:
		return False
	return Decimal(left).quantize(Decimal("0.01")) == Decimal(right).quantize(Decimal("0.01"))


def normalize_choice(value, valid_choices, default=""):
	return value if value in valid_choices else default


def format_br_date(value, empty_value="-"):
	return value.strftime("%d/%m/%Y") if value else empty_value


def format_brl_currency(value, empty_value="-"):
	if value is None:
		return empty_value

	int_part, dec_part = f"{abs(value):.2f}".split(".")
	int_formatted = "{:,}".format(int(int_part)).replace(",", ".")
	signal = "-" if value < 0 else ""
	return f"R$ {signal}{int_formatted},{dec_part}"


def format_brl_amount(value, empty_value="-", include_symbol=False):
	formatted = format_brl_currency(value, empty_value=empty_value)
	if formatted == empty_value or include_symbol:
		return formatted
	return formatted.removeprefix("R$ ")


def parse_brl_decimal(value, default=None):
	if value is None:
		return default

	if isinstance(value, Decimal):
		return value

	normalized = str(value).strip()
	if not normalized:
		return default

	normalized = normalized.replace("R$", "").replace(" ", "")
	if "," in normalized:
		normalized = normalized.replace(".", "").replace(",", ".")

	try:
		return Decimal(normalized)
	except (InvalidOperation, ValueError):
		return default


def safe_split(line, keyword, index=1):
	parts = line.split(keyword)
	if len(parts) > index:
		return parts[index].strip()
	return ""


def parse_br_date(date_str):
	try:
		if not date_str:
			return None
		return datetime.strptime(date_str.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
	except ValueError:
		return None


def extract_text_between(full_text, start_anchor, end_anchor):
	if full_text is None:
		return ""

	start_idx = full_text.find(start_anchor)
	if start_idx == -1:
		return ""

	start_idx += len(start_anchor)
	end_idx = full_text.find(end_anchor, start_idx)
	if end_idx == -1:
		end_idx = full_text.find("\n", start_idx)

	return full_text[start_idx:end_idx].replace("\n", "").strip()


def split_pdf_to_temp_pages(arquivo_pdf):
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


def processar_pdf_comprovantes(pdf_file):
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

		credor_encontrado = None

		padrao_doc = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2}")
		documentos = padrao_doc.findall(texto_flat)
		documentos_encontrados = []
		for doc in documentos:
			doc_norm = normalize_document(doc)
			if doc_norm and doc_norm != cnpj_orgao_norm:
				credor = Credor.objects.filter(cpf_cnpj=doc).first()
				documentos_encontrados.append({"doc": doc, "credor": credor})
				if credor and not credor_encontrado:
					credor_encontrado = credor

		contas_encontradas = []
		padrao_conta = re.compile(r"AGENCIA:\s*([\d-]+)\s*CONTA:\s*([\d.-]+[Xx]?)")
		contas = padrao_conta.findall(texto_flat)
		for agencia, conta in contas:
			agencia_norm, conta_norm = normalize_account(agencia, conta)
			if agencia_norm != agencia_orgao_norm or conta_norm != conta_orgao_norm:
				conta_db = ContasBancarias.objects.filter(agencia=agencia, conta=conta_norm).first()
				titular = conta_db.titular if conta_db else None
				contas_encontradas.append({"agencia": agencia, "conta": conta_norm, "credor": titular})
				if titular and not credor_encontrado:
					credor_encontrado = titular

		data_pagamento = ""
		padrao_data = re.compile(
			r"(?:DATA(?:\s*DO PAGAMENTO|\s*DA TRANSFERENCIA)?|DEBITO EM)\s*:?\s*(\d{2}/\d{2}/\d{4})",
			re.IGNORECASE,
		)
		match_data = padrao_data.search(texto_flat)
		if match_data:
			partes = match_data.group(1).split("/")
			if len(partes) == 3:
				data_pagamento = f"{partes[2]}-{partes[1]}-{partes[0]}"

		numero_comprovante = ""
		padrao_autenticacao = re.compile(
			r"NR\.AUTENTICACAO\s*([A-Z0-9]\.[A-Z0-9]{3}\.[A-Z0-9]{3}\.[A-Z0-9]{3}\.[A-Z0-9]{3}\.[A-Z0-9]{3})",
			re.IGNORECASE,
		)
		autenticacao_match = padrao_autenticacao.search(texto_flat)
		if autenticacao_match:
			numero_comprovante = autenticacao_match.group(1)

		resultados.append({
			**pagina_info,
			"credor_extraido": credor_encontrado.nome if credor_encontrado else None,
			"valor_extraido": valor_float,
			"data_pagamento": data_pagamento,
			"numero_comprovante": numero_comprovante,
			"documentos_encontrados": documentos_encontrados,
			"contas_encontradas": contas_encontradas,
		})
	return resultados


def mesclar_pdfs_em_memoria(lista_arquivos):
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


def gerar_csv_relatorio(queryset, tipo_relatorio):
	"""Gera resposta CSV para o tipo de relatório solicitado."""
	import csv
	from django.http import HttpResponse

	response = HttpResponse(content_type='text/csv')
	response['Content-Disposition'] = f'attachment; filename="relatorio_{tipo_relatorio}.csv"'
	response.write('\ufeff'.encode('utf8'))
	writer = csv.writer(response, delimiter=';')

	mapa_relatorios = {
		'processos': (
			['ID', 'Empenho', 'Credor', 'Valor Bruto', 'Valor Líquido', 'Status', 'Data Pagamento'],
			lambda p: [
				p.id,
				p.n_nota_empenho,
				p.credor.nome if p.credor else '',
				p.valor_bruto,
				p.valor_liquido,
				p.status.status_choice if p.status else '',
				p.data_pagamento,
			],
		),
		'diarias': (
			['ID', 'Beneficiário', 'Proponente', 'Período', 'Destino', 'Valor', 'Status'],
			lambda d: [
				d.id,
				d.beneficiario.nome if d.beneficiario else '',
				d.proponente.get_full_name() if d.proponente else '',
				f'{d.data_saida} a {d.data_retorno}',
				d.cidade_destino,
				d.valor_total,
				d.status.status_choice if d.status else '',
			],
		),
		'impostos': (
			['ID', 'NF', 'Processo Pai', 'Código', 'Valor Retido', 'Competência', 'Processo Pagamento'],
			lambda i: [
				i.id,
				i.nota_fiscal.numero_nota_fiscal,
				i.nota_fiscal.processo.id,
				i.codigo.codigo if i.codigo else '',
				i.valor,
				i.competencia,
				i.processo_pagamento.id if i.processo_pagamento else 'Pendente',
			],
		),
	}

	cabecalhos, extrator = mapa_relatorios.get(tipo_relatorio, (['Erro'], lambda x: ['Tipo não configurado']))
	writer.writerow(cabecalhos)
	for obj in queryset:
		writer.writerow(extrator(obj))
	return response




def gerar_faturas_do_mes(ano, mes):
	import datetime
	from django.db.models import Q
	from credores.models import ContaFixa, FaturaMensal

	data_ref = datetime.date(ano, mes, 1)
	contas_ativas = ContaFixa.objects.filter(ativa=True).filter(
		Q(data_inicio__year__lt=ano) | Q(data_inicio__year=ano, data_inicio__month__lte=mes)
	)
	for conta in contas_ativas:
		FaturaMensal.objects.get_or_create(conta_fixa=conta, mes_referencia=data_ref)




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
	"gerar_csv_relatorio",
	"gerar_faturas_do_mes",
	"PdfMergeError",
]
