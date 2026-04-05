"""PDF reading and text extraction utilities.

Strictly for *reading* PDFs. Imports: pdfplumber, PyPDF2/pypdf.
Also includes SISCAC payment reconciliation which operates on extracted data.
"""

import io
import re
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pdfplumber
import PyPDF2
from pypdf import PdfReader, PdfWriter
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from .text_helpers import (
    parse_brl_decimal,
    extract_text_between,
    normalize_account,
    normalize_document,
)

'''============================'''
'''MULTIPURPOSE EXTRACTION TOOLS'''
'''============================'''


def split_pdf_to_temp_pages(arquivo_pdf):
    """
    Divide um PDF em páginas individuais e salva cada uma em armazenamento
    temporário (prefixo temp/).

    Retorna uma lista de dicts com:
      - temp_path: caminho no default_storage
      - url: URL pública do arquivo temporário
      - pagina: número da página (1-indexado)
    """
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
            'temp_path': caminho_salvo,
            'url': default_storage.url(caminho_salvo),
            'pagina': numero_pagina + 1,
        })

    return paginas

'''============================'''
'''SISCAC EXTRACTION - DOCUMENTOS ORÇAMENTÁRIOS'''
'''============================'''

def extract_siscac_data(pdf_file):
    """Extrai campos básicos de empenho, liquidação e pagamento de PDF SISCAC."""
    from .text_helpers import parse_br_date

    pages_dict = sort_pages(pdf_file)
    data = {}

    with pdfplumber.open(pdf_file) as pdf:
        if pages_dict["empenho"]:
            text = pdf.pages[pages_dict["empenho"][0]].extract_text()

            data['n_nota_empenho'] = extract_text_between(text, "Número do Registro:", "Data:")
            raw_date = extract_text_between(text, "Data:", "Ano do Exercício:")

            data['data_empenho'] = parse_br_date(raw_date)
            data['ano_exercicio'] = extract_text_between(text, "Ano do Exercício:", "\n")
            data['credor'] = extract_text_between(text, "Credor:", "\n")
            total_bruto = Decimal("0")

            for p_idx in pages_dict["empenho"]:
                p_text = pdf.pages[p_idx].extract_text()
                val_str = extract_text_between(p_text, "Valor:", "\n")
                if val_str:
                    total_bruto += parse_brl_decimal(val_str, default=Decimal("0"))

            data['valor_bruto'] = float(total_bruto)

        obs_list = []
        for p_idx in pages_dict["liquidacao"]:
            text = pdf.pages[p_idx].extract_text()
            obs_list.append(extract_text_between(text, "LIQUIDAÇÃO - ", "Registro Contábil:"))

        data['observacao'] = obs_list

        total_liquido = Decimal("0")
        for p_idx in pages_dict["pagamento"]:
            text = pdf.pages[p_idx].extract_text()
            val_str = extract_text_between(text, "Valor Líquido:", "\n")
            if val_str:
                try:
                    total_liquido += parse_brl_decimal(val_str, default=Decimal("0"))
                except Exception:
                    pass

        if total_liquido > 0:
            data['valor_liquido'] = float(total_liquido)

    return data


def sort_pages(pdf_file):
    """Classifica páginas de relatório SISCAC por tipo de bloco identificado no texto."""
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



'''============================'''
'''SISCAC EXTRACTION - RELATÓRIO DE PAGAMENTOS'''
'''============================'''

def parse_siscac_report(pdf_file):
    """Lê relatório de pagamentos SISCAC e consolida lançamentos por número de pagamento."""
    pattern_payment = re.compile(
        r'^(20\d{2}PG\d{5})\s+(.*?)\s+(20\d{2}NE\d{5}).*?([\d.,]+)$'
    )
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

'''============================'''
'''DOCUMENTO FINANCEIRO EXTRACTION - BOLETO'''
'''============================'''

def interpretar_linha(linha, tipo):
    """Calcula o valor e o vencimento baseado no tipo (Banco ou Arrecadação)."""
    if tipo == 'bancario':
        valor_liquido = float(linha[-10:]) / 100
        fator_vencimento = int(linha[33:37])
        vencimento = ''

        if fator_vencimento > 0:
            base_data = datetime(1997, 10, 7)
            data_vencimento = base_data + timedelta(days=fator_vencimento)

            # Resolve a virada do calendário da Febraban (Fev/2025)
            if data_vencimento.year < 2015:
                data_vencimento += timedelta(days=9000)

            vencimento = data_vencimento.date().isoformat()

        return {'valor': valor_liquido, 'vencimento': vencimento}

    elif tipo == 'arrecadacao':
        # Arrecadação tem 4 blocos de 12. Ignoramos o último dígito de cada bloco.
        payload = linha[0:11] + linha[12:23] + linha[24:35] + linha[36:47]
        valor_liquido = float(payload[4:15]) / 100
        return {'valor': valor_liquido, 'vencimento': ''}

    return None

def processar_pdf_boleto(pdf_file):
    """Localiza linha digitável de boleto/arrecadação em PDF e retorna payload normalizado."""
    leitor = PyPDF2.PdfReader(pdf_file)
    texto = " ".join([pagina.extract_text() for pagina in leitor.pages if pagina.extract_text()])

    texto = re.sub(r'\s+', ' ', texto)

    padrao = r'(?<!\d)(?:\d[\s\.\-]*){47,55}(?!\d)'
    candidatos = re.findall(padrao, texto)

    for candidato in candidatos:
        numeros = re.sub(r'\D', '', candidato)

        codigo_encontrado = None

        # Regra 1: Conta de Consumo (Ex: Celesc, Vivo) - Exatos 48 dígitos começando com '8'
        if len(numeros) == 48 and numeros.startswith('8'):
            codigo_encontrado = numeros

        # Regra 2: Boleto Bancário Padrão - Exatos 47 dígitos
        elif len(numeros) == 47:
            codigo_encontrado = numeros

        # Regra 3: Bancário com prefixo grudado (Ex: Bradesco) - Pegamos os últimos 47
        elif 47 < len(numeros) <= 55:
            codigo_encontrado = numeros[-47:]

        if codigo_encontrado:
            return {
                'codigo_barras': codigo_encontrado,
                'valor': 0,
                'vencimento': '',
            }

    raise ValueError("Linha digitável válida não encontrada no PDF.")

'''============================'''
'''DOCUMENTO FINANCEIRO EXTRACTION - COMPROVANTE DE PAGAMENTO'''
'''============================'''

def processar_pdf_comprovantes(pdf_file):
    """Fatia comprovantes em páginas e extrai credor, valor, data e autenticação por regex."""
    from processos.models import Credor, ContasBancarias

    CNPJ_ORGAO = '82.894.098/0001-32'
    AGENCIA_ORGAO = '3582-3'
    CONTA_ORGAO_LIMPA = '7429-2'

    cnpj_orgao_norm = normalize_document(CNPJ_ORGAO)
    agencia_orgao_norm, conta_orgao_norm = normalize_account(AGENCIA_ORGAO, CONTA_ORGAO_LIMPA)

    paginas_temp = split_pdf_to_temp_pages(pdf_file)
    resultados = []

    for pagina_info in paginas_temp:
        with default_storage.open(pagina_info['temp_path'], 'rb') as f:
            with pdfplumber.open(f) as pdf_leitor:
                texto = pdf_leitor.pages[0].extract_text() or ""

        texto_flat = re.sub(r'\s+', ' ', texto)

        # --- PARTE A: EXTRAÇÃO DO VALOR ---
        padrao_valor = re.compile(
            r'(?:VALOR TOTAL|VALOR DO DOCUMENTO|VALOR COBRADO|VALOR EM DINHEIRO|VALOR)\s*:?\s*(?:R\$\s*)?([\d.,]+)',
            re.IGNORECASE,
        )

        valor_float = 0.00
        for match_valor in padrao_valor.finditer(texto_flat):
            valor_str = match_valor.group(1).replace('.', '').replace(',', '.')
            try:
                valor_float = float(valor_str)
                break
            except ValueError:
                pass

        # --- PARTE B: IDENTIFICAÇÃO DO CREDOR ---
        credor_encontrado = None

        # Método Primário: identificação por CNPJ/CPF
        padrao_doc = re.compile(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2}')
        documentos = padrao_doc.findall(texto_flat)
        documentos_encontrados = []
        for doc in documentos:
            doc_norm = normalize_document(doc)
            if doc_norm and doc_norm != cnpj_orgao_norm:
                credor = Credor.objects.filter(cpf_cnpj=doc).first()
                documentos_encontrados.append({'doc': doc, 'credor': credor})
                if credor and not credor_encontrado:
                    credor_encontrado = credor

        # Método Secundário: identificação por Conta Bancária
        contas_encontradas = []
        padrao_conta = re.compile(r'AGENCIA:\s*([\d-]+)\s*CONTA:\s*([\d.-]+[Xx]?)')
        contas = padrao_conta.findall(texto_flat)
        for agencia, conta in contas:
            agencia_norm, conta_norm = normalize_account(agencia, conta)
            if agencia_norm != agencia_orgao_norm or conta_norm != conta_orgao_norm:
                conta_db = ContasBancarias.objects.filter(agencia=agencia, conta=conta_norm).first()
                titular = conta_db.titular if conta_db else None
                contas_encontradas.append({'agencia': agencia, 'conta': conta_norm, 'credor': titular})
                if titular and not credor_encontrado:
                    credor_encontrado = titular

        # --- PARTE B.2: EXTRAÇÃO DA DATA DE PAGAMENTO ---
        data_pagamento = ''
        padrao_data = re.compile(
            r'(?:DATA(?:\s*DO PAGAMENTO|\s*DA TRANSFERENCIA)?|DEBITO EM)\s*:?\s*(\d{2}/\d{2}/\d{4})',
            re.IGNORECASE,
        )
        match_data = padrao_data.search(texto_flat)
        if match_data:
            partes = match_data.group(1).split('/')
            if len(partes) == 3:
                data_pagamento = f"{partes[2]}-{partes[1]}-{partes[0]}"

        # --- PARTE B.3: EXTRAÇÃO DO NR. AUTENTICACAO (Banco do Brasil) ---
        numero_comprovante = ''
        padrao_autenticacao = re.compile(
            r'NR\.AUTENTICACAO\s*([A-Z0-9]\.[A-Z0-9]{3}\.[A-Z0-9]{3}\.[A-Z0-9]{3}\.[A-Z0-9]{3}\.[A-Z0-9]{3})',
            re.IGNORECASE
        )
        autenticacao_match = padrao_autenticacao.search(texto_flat)
        if autenticacao_match:
            numero_comprovante = autenticacao_match.group(1)

        # --- EMPACOTAMENTO ---
        resultados.append({
            **pagina_info,
            'credor_extraido': credor_encontrado.nome if credor_encontrado else None,
            'valor_extraido': valor_float,
            'data_pagamento': data_pagamento,
            'numero_comprovante': numero_comprovante,
            'documentos_encontrados': documentos_encontrados,
            'contas_encontradas': contas_encontradas,
        })
    for item in resultados:
        print(item)
    return resultados


__all__ = [
    "split_pdf_to_temp_pages",
    "extract_siscac_data",
    "sort_pages",
    "parse_siscac_report",
    "interpretar_linha",
    "processar_pdf_boleto",
    "processar_pdf_comprovantes",
]