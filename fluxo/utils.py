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


def merge_canvas_with_template(canvas_io, template_path):
	canvas_io.seek(0)
	canvas_reader = PdfReader(canvas_io)
	canvas_page = canvas_reader.pages[0]

	writer = PdfWriter()
	if template_path:
		try:
			with open(template_path, "rb") as template_file:
				template_reader = PdfReader(template_file)
				template_page = template_reader.pages[0]
				template_page.merge_page(canvas_page)
				writer.add_page(template_page)
		except FileNotFoundError:
			writer.add_page(canvas_page)
	else:
		writer.add_page(canvas_page)

	output = io.BytesIO()
	writer.write(output)
	output.seek(0)
	return output


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


def decode_csv_file(csv_file, encodings, error_message):
	raw = csv_file.read()
	if isinstance(raw, str):
		return raw, None
	for encoding in encodings:
		try:
			return raw.decode(encoding), None
		except UnicodeDecodeError:
			continue
	return None, error_message


def build_csv_dict_reader(
	csv_file,
	*,
	encodings,
	encoding_error_message,
	required_columns=None,
	missing_columns_message_prefix='Cabeçalho inválido. Colunas ausentes:',
):
	import csv

	decoded, error = decode_csv_file(csv_file, encodings, encoding_error_message)
	if error:
		return None, error
	reader = csv.DictReader(io.StringIO(decoded))
	if required_columns is None:
		return reader, None
	fieldnames = set(reader.fieldnames or [])
	if not set(required_columns).issubset(fieldnames):
		faltando = set(required_columns) - fieldnames
		return None, f"{missing_columns_message_prefix} {', '.join(sorted(faltando))}."
	return reader, None


def importar_credores_csv(csv_file):
	from credores.models import CargosFuncoes, ContasBancarias, Credor
	from django.db import DatabaseError

	resultados = {'sucessos': 0, 'erros': []}
	reader, erro = build_csv_dict_reader(
		csv_file,
		encodings=('utf-8-sig', 'latin-1'),
		encoding_error_message='Erro de codificação: não foi possível ler o CSV.',
	)
	if erro:
		resultados['erros'].append(erro)
		return resultados

	for row in reader:
		try:
			cpf_cnpj_limpo = row['CPF_CNPJ'].replace('.', '').replace('-', '').replace('/', '').replace(' ', '').strip()
			tipo = 'PF' if len(cpf_cnpj_limpo) == 11 else 'PJ'
			defaults = {'nome': row['NOME'].strip(), 'tipo': tipo}
			grupo_nome = row.get('GRUPO', '').strip()
			cargo_nome = row.get('CARGO_FUNCAO', '').strip()
			if grupo_nome and cargo_nome:
				cargo_obj, _ = CargosFuncoes.objects.get_or_create(grupo=grupo_nome, cargo_funcao=cargo_nome)
				defaults['cargo_funcao'] = cargo_obj

			credor, _ = Credor.objects.get_or_create(cpf_cnpj=cpf_cnpj_limpo, defaults=defaults)
			banco = row.get('BANCO', '').strip() or None
			agencia = row.get('AGENCIA', '').strip() or None
			conta_num = row.get('CONTA', '').strip() or None
			pix = row.get('PIX', '').strip() or None

			if banco or agencia or conta_num:
				conta_bancaria, _ = ContasBancarias.objects.get_or_create(
					titular=credor,
					banco=banco,
					agencia=agencia,
					conta=conta_num,
				)
				if credor.conta_id != conta_bancaria.pk:
					credor.conta = conta_bancaria
					credor.save(update_fields=['conta'])

			if pix and credor.chave_pix != pix:
				credor.chave_pix = pix
				credor.save(update_fields=['chave_pix'])

			resultados['sucessos'] += 1
		except (KeyError, AttributeError, ValueError, TypeError, DatabaseError) as e:
			resultados['erros'].append(f"Linha {reader.line_num}: {e}")
	return resultados


def importar_contas_fixas_csv(csv_file):
	from credores.models import ContaFixa, Credor
	from django.db import DatabaseError

	resultados = {'sucessos': 0, 'erros': []}
	reader, erro = build_csv_dict_reader(
		csv_file,
		encodings=('utf-8-sig', 'latin-1'),
		encoding_error_message='Erro de codificação: não foi possível ler o CSV.',
	)
	if erro:
		resultados['erros'].append(erro)
		return resultados

	for row in reader:
		try:
			nome_credor = row['NOME_CREDOR'].strip()
			credor = Credor.objects.filter(nome__iexact=nome_credor).first()
			if not credor:
				resultados['erros'].append(f"Linha {reader.line_num}: Credor '{nome_credor}' não encontrado.")
				continue
			ContaFixa.objects.get_or_create(
				credor=credor,
				referencia=row['DETALHAMENTO'].strip(),
				defaults={'dia_vencimento': int(row['DIA_VENCIMENTO']), 'ativa': True},
			)
			resultados['sucessos'] += 1
		except ValueError as e:
			resultados['erros'].append(f"Linha {reader.line_num}: {e}")
		except (KeyError, AttributeError, TypeError, DatabaseError) as e:
			resultados['erros'].append(f"Linha {reader.line_num}: {e}")
	return resultados


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


class DiariaCsvValidationError(Exception):
	"""Erro de validação de linha de diária em importação CSV."""


def _parse_diaria_row(row, line_num):
	from credores.models import Credor

	nome = row.get('NOME_BENEFICIARIO', '').strip()
	credor = Credor.objects.filter(nome__iexact=nome, tipo='PF').first() or Credor.objects.filter(nome__icontains=nome, tipo='PF').first()
	if not credor:
		raise DiariaCsvValidationError(f"Linha {line_num}: Beneficiário '{nome}' não encontrado no sistema.")

	try:
		data_saida = datetime.strptime(row['DATA_SAIDA'].strip(), '%d/%m/%Y').date()
		data_retorno = datetime.strptime(row['DATA_RETORNO'].strip(), '%d/%m/%Y').date()
	except ValueError:
		raise DiariaCsvValidationError(f"Linha {line_num}: Data inválida. Use o formato DD/MM/AAAA.")

	if data_retorno < data_saida:
		raise DiariaCsvValidationError(
			f"Linha {line_num}: Data de retorno ({row['DATA_RETORNO'].strip()}) não pode ser anterior à data de saída ({row['DATA_SAIDA'].strip()})."
		)

	try:
		qtd = Decimal(row['QUANTIDADE_DIARIAS'].strip().replace(',', '.'))
		if qtd <= 0:
			raise InvalidOperation
	except InvalidOperation:
		raise DiariaCsvValidationError(
			f"Linha {line_num}: Quantidade de diárias inválida: {row['QUANTIDADE_DIARIAS']}."
		)

	return {
		'credor': credor,
		'data_saida': data_saida,
		'data_retorno': data_retorno,
		'cidade_origem': row['CIDADE_ORIGEM'].strip(),
		'cidade_destino': row['CIDADE_DESTINO'].strip(),
		'objetivo': row['OBJETIVO'].strip(),
		'quantidade_diarias': qtd,
	}


def _open_diaria_csv(csv_file):
	colunas = {
		'NOME_BENEFICIARIO', 'DATA_SAIDA', 'DATA_RETORNO', 'CIDADE_ORIGEM', 'CIDADE_DESTINO', 'OBJETIVO', 'QUANTIDADE_DIARIAS'
	}
	return build_csv_dict_reader(
		csv_file,
		encodings=('utf-8',),
		encoding_error_message='Erro de codificação: verifique se o arquivo está salvo em UTF-8.',
		required_columns=colunas,
		missing_columns_message_prefix='Cabeçalho inválido. Colunas ausentes:',
	)


def _gerar_anexar_scd_e_criar_assinatura(diaria, usuario_logado):
	from verbas_indenizatorias.services.diarias import gerar_e_anexar_scd_diaria

	gerar_e_anexar_scd_diaria(diaria, usuario_logado)


def preview_diarias_lote(csv_file):
	resultado = {'preview': [], 'erros': []}
	reader, erro = _open_diaria_csv(csv_file)
	if erro:
		resultado['erros'].append(erro)
		return resultado

	for row in reader:
		try:
			parsed = _parse_diaria_row(row, reader.line_num)
		except DiariaCsvValidationError as exc:
			resultado['erros'].append(str(exc))
			continue

		credor = parsed['credor']
		resultado['preview'].append({
			'beneficiario_id': credor.pk,
			'beneficiario_nome': credor.nome,
			'data_saida': parsed['data_saida'].strftime('%Y-%m-%d'),
			'data_retorno': parsed['data_retorno'].strftime('%Y-%m-%d'),
			'data_saida_display': parsed['data_saida'].strftime('%d/%m/%Y'),
			'data_retorno_display': parsed['data_retorno'].strftime('%d/%m/%Y'),
			'cidade_origem': parsed['cidade_origem'],
			'cidade_destino': parsed['cidade_destino'],
			'objetivo': parsed['objetivo'],
			'quantidade_diarias': str(parsed['quantidade_diarias']),
		})
	return resultado


def confirmar_diarias_lote(preview_items, usuario_logado):
	from credores.models import Credor
	from verbas_indenizatorias.models import Diaria

	resultados = {'sucessos': 0, 'erros': []}
	for item in preview_items:
		credor = Credor.objects.filter(pk=item['beneficiario_id'], tipo='PF').first()
		if credor is None:
			resultados['erros'].append(f"Beneficiário com ID {item['beneficiario_id']} não encontrado ao confirmar.")
			continue

		nova_diaria = Diaria.objects.create(
			beneficiario=credor,
			proponente=usuario_logado,
			data_saida=datetime.strptime(item['data_saida'], '%Y-%m-%d').date(),
			data_retorno=datetime.strptime(item['data_retorno'], '%Y-%m-%d').date(),
			cidade_origem=item['cidade_origem'],
			cidade_destino=item['cidade_destino'],
			objetivo=item['objetivo'],
			quantidade_diarias=Decimal(item['quantidade_diarias']),
			autorizada=False,
		)
		nova_diaria.avancar_status('SOLICITADA')
		try:
			_gerar_anexar_scd_e_criar_assinatura(nova_diaria, usuario_logado)
		except (OSError, RuntimeError, TypeError, ValueError) as e:
			resultados['erros'].append(f"Diária {nova_diaria.numero_siscac or nova_diaria.id}: SCD não gerado ({e})")
		resultados['sucessos'] += 1
	return resultados


def sync_diarias_siscac_csv(csv_file):
	import csv

	from credores.models import Credor
	from verbas_indenizatorias.models import Diaria, StatusChoicesVerbasIndenizatorias

	resultados = {'criadas': 0, 'atualizadas': 0, 'erros': []}
	content = csv_file.read().decode('utf-8')
	reader = csv.reader(io.StringIO(content), delimiter=';')

	for line in reader:
		if line and line[0].strip() == 'Número':
			break

	for row in reader:
		if not row or not row[0].strip():
			continue
		try:
			numero_csv = row[0].strip()
			row_name = row[1].strip() if len(row) > 1 else ''
			destino = row[3].strip() if len(row) > 3 else ''
			saida_str = row[4].strip() if len(row) > 4 else ''
			retorno_str = row[6].strip() if len(row) > 6 else ''
			situacao_str = row[7].strip() if len(row) > 7 else ''
			motivo = row[8].strip() if len(row) > 8 else ''
			qtd_str = row[10].strip() if len(row) > 10 else ''
			valor_str = row[13].strip() if len(row) > 13 else ''
		except IndexError:
			resultados['erros'].append(f'Linha malformada: {row}')
			continue

		if not row_name:
			continue

		try:
			saida = datetime.strptime(saida_str, '%d/%m/%Y').date() if saida_str else None
			retorno = datetime.strptime(retorno_str, '%d/%m/%Y').date() if retorno_str else None
		except ValueError:
			resultados['erros'].append(f'Data inválida na linha com Nº {numero_csv}')
			continue

		try:
			valor_diaria = Decimal(valor_str.replace('.', '').replace(',', '.')) if valor_str else None
		except InvalidOperation:
			valor_diaria = None

		try:
			quantidade = Decimal(qtd_str.replace(',', '.')) if qtd_str else Decimal('1')
		except InvalidOperation:
			quantidade = Decimal('1')

		credor = Credor.objects.filter(nome__icontains=row_name).first()
		if credor is None:
			resultados['erros'].append(f'Credor não encontrado para: {row_name}')
			continue

		status_obj = None
		if situacao_str:
			status_obj = StatusChoicesVerbasIndenizatorias.objects.filter(status_choice__iexact=situacao_str).first()
			if status_obj is None:
				status_obj = StatusChoicesVerbasIndenizatorias.objects.create(status_choice=situacao_str)

		_, created = Diaria.objects.update_or_create(
			numero_siscac=numero_csv,
			defaults={
				'beneficiario': credor,
				'data_saida': saida,
				'data_retorno': retorno,
				'cidade_destino': destino or '-',
				'cidade_origem': '-',
				'objetivo': motivo or '-',
				'quantidade_diarias': quantidade,
				'valor_total': valor_diaria,
				'status': status_obj,
			},
		)
		if created:
			resultados['criadas'] += 1
		else:
			resultados['atualizadas'] += 1

	return resultados


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
	"merge_canvas_with_template",
	"gerar_csv_relatorio",
	"importar_credores_csv",
	"importar_contas_fixas_csv",
	"gerar_faturas_do_mes",
	"preview_diarias_lote",
	"confirmar_diarias_lote",
	"sync_diarias_siscac_csv",
	"PdfMergeError",
]
