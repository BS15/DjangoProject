import io
import os
import pdfplumber
import PyPDF2
import re
import textwrap
import uuid
from collections import Counter
from decimal import Decimal
from pypdf import PdfWriter, PdfReader
from datetime import datetime, timedelta
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db.models import Q
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def mesclar_pdfs_em_memoria(lista_arquivos):
    """
    Recebe uma lista de arquivos (podem ser caminhos no disco ou UploadedFiles da RAM)
    e retorna um buffer de memória contendo o PDF mesclado.
    """
    merger = PdfWriter()

    try:
        for arquivo in lista_arquivos:
            # O pypdf é inteligente o suficiente para aceitar tanto a string (caminho)
            # quanto o objeto de arquivo do Django (request.FILES)
            if arquivo:
                merger.append(arquivo)

        # Cria um arquivo virtual na memória RAM
        output_pdf = io.BytesIO()
        merger.write(output_pdf)
        merger.close()

        # Volta o "cursor" do arquivo para o início, pronto para ser lido
        output_pdf.seek(0)

        return output_pdf

    except Exception as e:
        print(f"Erro na mesclagem de PDFs: {e}")
        return None

def safe_split(line, keyword, index=1):
    parts = line.split(keyword)
    if len(parts) > index:
        return parts[index].strip()
    return ""

def parse_br_date(date_str):
    try:
        if not date_str: return None
        return datetime.strptime(date_str.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None

def extract_text_between(full_text, start_anchor, end_anchor):
    try:
        start_idx = full_text.find(start_anchor)
        if start_idx == -1: return ""
        start_idx += len(start_anchor)
        end_idx = full_text.find(end_anchor, start_idx)
        if end_idx == -1:
            end_idx = full_text.find("\n", start_idx)
        return full_text[start_idx:end_idx].replace("\n", "").strip()
    except:
        return ""

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

            data['n_nota_empenho'] = extract_text_between(text, "Número do Registro:", "Data:")
            raw_date = extract_text_between(text, "Data:", "Ano do Exercício:")

            data['data_empenho'] = parse_br_date(raw_date)
            data['ano_exercicio'] = extract_text_between(text, "Ano do Exercício:", "\n")
            data['credor'] = extract_text_between(text, "Credor:", "\n")
            total_bruto = 0.0

            for p_idx in pages_dict["empenho"]:
                p_text = pdf.pages[p_idx].extract_text()
                val_str = extract_text_between(p_text, "Valor:", "\n")
                if val_str:
                    total_bruto += float(val_str.replace(".", "").replace(",", "."))

            data['valor_bruto'] = total_bruto

        obs_list = []
        for p_idx in pages_dict["liquidacao"]:
            text = pdf.pages[p_idx].extract_text()
            obs_list.append(extract_text_between(text, "LIQUIDAÇÃO - ", "Registro Contábil:"))

        data['observacao'] = obs_list

        total_liquido = 0.0
        for p_idx in pages_dict["pagamento"]:
            text = pdf.pages[p_idx].extract_text()
            val_str = extract_text_between(text, "Valor Líquido:", "\n")
            if val_str:
                try:
                    clean_val = val_str.replace("R$", "").strip()
                    total_liquido += float(clean_val.replace(".", "").replace(",", "."))
                except:
                    pass

        if total_liquido > 0:
            data['valor_liquido'] = total_liquido

    return data


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

        # O vencimento vai vazio, pois será extraído do texto do PDF
        return {'valor': valor_liquido, 'vencimento': ''}

    return None


def processar_pdf_boleto(pdf_file):
    leitor = PyPDF2.PdfReader(pdf_file)
    texto = " ".join([pagina.extract_text() for pagina in leitor.pages if pagina.extract_text()])

    # Transforma quebras de linha em espaços para facilitar a leitura
    texto = re.sub(r'\s+', ' ', texto)

    # A MÁGICA: Busca um bloco de 47 a 55 números que SÓ podem estar separados por
    # espaço, ponto ou traço. Se tiver barra (/) ou vírgula (,), ele ignora.
    padrao = r'(?<!\d)(?:\d[\s\.\-]*){47,55}(?!\d)'

    candidatos = re.findall(padrao, texto)

    for candidato in candidatos:
        # Tira os espaços, pontos e traços do candidato, deixando só os números
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

        # Se achou o código e passou nas regras, devolve para a tela!
        if codigo_encontrado:
            return {
                'codigo_barras': codigo_encontrado,
                'valor': 0,  # Mantido zerado para o Javascript não dar erro
                'vencimento': ''  # Mantido vazio para o Javascript não dar erro
            }

    raise ValueError("Linha digitável válida não encontrada no PDF.")


def processar_pdf_comprovantes(pdf_file):
    from .models import Credor, ContasBancarias

    CNPJ_ORGAO = '82.894.098/0001-32'
    AGENCIA_ORGAO = '3582-3'
    CONTA_ORGAO_LIMPA = '7429-2'

    paginas_temp = split_pdf_to_temp_pages(pdf_file)
    resultados = []

    for pagina_info in paginas_temp:
        with default_storage.open(pagina_info['temp_path'], 'rb') as f:
            with pdfplumber.open(f) as pdf_leitor:
                texto = pdf_leitor.pages[0].extract_text() or ""

        # A MÁGICA: Transforma todo o texto da página (com tabelas e colunas) em uma única linha reta
        texto_flat = re.sub(r'\s+', ' ', texto)

        # --- PARTE A: EXTRAÇÃO DO VALOR ---
        # Busca as palavras-chave, ignora símbolos perdidos no meio, e captura o padrão "1.500,00"
        padrao_valor = re.compile(
            r'(?:VALOR TOTAL|VALOR DO DOCUMENTO|VALOR COBRADO|VALOR EM DINHEIRO|VALOR(?:\s*:)?\s*(?:R\$)?)\s*([\d.,]+)',
            re.IGNORECASE
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
            if doc != CNPJ_ORGAO:
                credor = Credor.objects.filter(cpf_cnpj=doc).first()
                documentos_encontrados.append({'doc': doc, 'credor': credor})
                if credor and not credor_encontrado:
                    credor_encontrado = credor

        # Método Secundário: identificação por Conta Bancária
        contas_encontradas = []
        padrao_conta = re.compile(r'AGENCIA:\s*([\d-]+)\s*CONTA:\s*([\d.-]+[Xx]?)')
        contas = padrao_conta.findall(texto_flat)
        for agencia, conta in contas:
            conta_limpa = conta.replace('.', '')
            if agencia != AGENCIA_ORGAO or conta_limpa != CONTA_ORGAO_LIMPA:
                conta_db = ContasBancarias.objects.filter(agencia=agencia, conta=conta_limpa).first()
                titular = conta_db.titular if conta_db else None
                contas_encontradas.append({'agencia': agencia, 'conta': conta_limpa, 'credor': titular})
                if titular and not credor_encontrado:
                    credor_encontrado = titular

        # --- PARTE B.2: EXTRAÇÃO DA DATA DE PAGAMENTO ---
        data_pagamento = ''
        padrao_data = re.compile(
            r'(?:DATA(?:\s*DO PAGAMENTO|\s*DA TRANSFERENCIA)?|DEBITO EM(?:\s*:)?)\s*(\d{2}/\d{2}/\d{4})',
            re.IGNORECASE
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

def gerar_termo_auditoria(processo, usuario_nome="Conselheiro Fiscal"):
    """Gera uma folha de rosto em PDF na memória atestando o fechamento."""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Cabeçalho
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2.0, height - 100, "TERMO DE ENCERRAMENTO E AUDITORIA FISCAL")

    # Dados do Processo
    p.setFont("Helvetica", 12)
    p.drawString(100, height - 160, f"Processo Nº: {processo.id}")
    p.drawString(100, height - 180, f"Credor: {processo.credor}")
    p.drawString(100, height - 200, f"Valor Consolidado: R$ {processo.valor_liquido}")
    p.drawString(100, height - 220, f"Data/Hora do Fechamento: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    # Declaração
    texto_declaracao = (
        "Certifico que os documentos anexos a este processo foram conferidos em sua "
        "integralidade, consolidados em arquivo único e aprovados pelo Conselho Fiscal, "
        "estando aptos para arquivamento definitivo."
    )
    p.drawString(100, height - 280, texto_declaracao[:90])
    p.drawString(100, height - 300, texto_declaracao[90:])

    # Assinatura
    p.line(150, height - 450, 450, height - 450)
    p.drawCentredString(width / 2.0, height - 470, f"Assinado eletronicamente por: {usuario_nome}")

    # Rodapé de segurança
    p.setFont("Helvetica-Oblique", 8)
    p.drawString(50, 50, f"Documento gerado automaticamente pelo System X - Integridade Garantida.")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

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

        # Gera um nome único para evitar colisões
        nome_temp = f"temp_comprovante_{uuid.uuid4().hex[:8]}_pag{numero_pagina + 1}.pdf"
        caminho_salvo = default_storage.save(f"temp/{nome_temp}", ContentFile(buffer.read()))

        paginas.append({
            'temp_path': caminho_salvo,
            'url': default_storage.url(caminho_salvo),
            'pagina': numero_pagina + 1,
        })

    return paginas


def fatiar_pdf_manual(arquivo_pdf):
    """
    Recebe um PDF, divide-o página a página e guarda ficheiros temporários.
    Retorna uma lista de dicts com temp_path, url e pagina.
    """
    return split_pdf_to_temp_pages(arquivo_pdf)


# ---------------------------------------------------------------------------
# Utilitários de geração de documentos PDF oficiais
# ---------------------------------------------------------------------------

# Proporção aproximada largura/tamanho-de-fonte para cálculo de quebra de linha (Helvetica).
_CHAR_WIDTH_RATIO = 0.55

# Altura reservada (em pontos) para os blocos de assinatura no rodapé.
_SIGNATURE_BLOCK_HEIGHT = 160

# Número máximo de entradas da trilha de auditoria exibidas no Parecer do Conselho.
_MAX_AUDIT_TRAIL_ENTRIES = 10

# Geometria do bloco de assinatura único (Termo de Autorização).
_AUTH_SIG_Y = 120
_AUTH_SIG_HALF_WIDTH = 130
_AUTH_SIG_DATE_OFFSET = 32

# Geometria dos blocos de assinatura triplos (Parecer do Conselho Fiscal).
_COUNCIL_SIG_Y = 110
_COUNCIL_SIG_WIDTH = 145

def merge_canvas_with_template(canvas_io, template_path):
    """
    Mescla um canvas PDF (BytesIO gerado pelo ReportLab) sobre um template PDF
    (papel timbrado), retornando o PDF final como BytesIO.

    O canvas é renderizado sobre o template, de modo que o papel timbrado
    sirva de fundo e o conteúdo gerado apareça por cima.
    """
    canvas_io.seek(0)
    template_reader = PdfReader(template_path)
    canvas_reader = PdfReader(canvas_io)

    writer = PdfWriter()
    template_page = template_reader.pages[0]
    canvas_page = canvas_reader.pages[0]

    # Sobrepõe o canvas (texto) sobre o template (papel timbrado como fundo)
    template_page.merge_page(canvas_page)
    writer.add_page(template_page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output


def _contar_paginas_documentos(processo):
    """
    Conta o número total de documentos e páginas nos DocumentoProcesso em PDF.
    Retorna uma tupla (total_documentos, total_paginas).
    """
    total_docs = 0
    total_pages = 0

    for doc in processo.documentos.all():
        total_docs += 1
        try:
            with doc.arquivo.open('rb') as f:
                reader = PdfReader(f)
                total_pages += len(reader.pages)
        except Exception:
            pass

    return total_docs, total_pages


def _formatar_moeda(valor):
    """Formata um valor decimal no padrão monetário brasileiro: R$ 1.234,56"""
    if valor is None:
        valor = 0
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _draw_wrapped_text(p, text, x, y, max_width, font_name="Helvetica", font_size=11, leading=16):
    """
    Desenha texto com quebra automática de linha no canvas ReportLab.
    Retorna a posição Y após o último texto desenhado.
    """
    if not text:
        return y
    p.setFont(font_name, font_size)
    chars_per_line = max(1, int(max_width / (font_size * _CHAR_WIDTH_RATIO)))
    lines = textwrap.wrap(str(text), width=chars_per_line)
    if not lines:
        lines = [str(text)]
    for line in lines:
        p.drawString(x, y, line)
        y -= leading
    return y


def gerar_pdf_autorizacao(processo):
    """
    Gera o PDF "Termo de Autorização de Pagamento" para o processo especificado.
    Retorna um BytesIO contendo o PDF final mesclado com o papel timbrado.
    """
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_left = 70
    margin_right = 70
    text_width = width - margin_left - margin_right

    y = height - 160

    # --- CABEÇALHO ---
    p.setFont("Helvetica-Bold", 13)
    p.drawCentredString(width / 2.0, y, "TERMO DE AUTORIZAÇÃO DE PAGAMENTO")
    y -= 18
    p.setFont("Helvetica-Bold", 12)
    p.drawCentredString(width / 2.0, y, f"PROCESSO Nº {processo.id}")
    y -= 30

    p.setLineWidth(0.5)
    p.line(margin_left, y, width - margin_right, y)
    y -= 20

    # --- DADOS DO CREDOR ---
    p.setFont("Helvetica-Bold", 11)
    p.drawString(margin_left, y, "DADOS DO CREDOR:")
    y -= 16
    p.setFont("Helvetica", 11)

    nome_credor = str(processo.credor.nome) if processo.credor and processo.credor.nome else "Não informado"
    cpf_cnpj = str(processo.credor.cpf_cnpj) if processo.credor and processo.credor.cpf_cnpj else "Não informado"

    p.drawString(margin_left, y, f"Nome / Razão Social:  {nome_credor}")
    y -= 16
    p.drawString(margin_left, y, f"CPF / CNPJ:           {cpf_cnpj}")
    y -= 24

    # --- COMPOSIÇÃO DO VALOR ---
    p.setFont("Helvetica-Bold", 11)
    p.drawString(margin_left, y, "COMPOSIÇÃO DO VALOR:")
    y -= 16
    p.setFont("Helvetica", 11)

    valor_bruto = processo.valor_bruto or 0
    valor_liquido = processo.valor_liquido or 0
    total_retencoes = valor_bruto - valor_liquido

    p.drawString(margin_left, y, f"Valor Bruto:                    {_formatar_moeda(valor_bruto)}")
    y -= 16
    p.drawString(margin_left, y, f"Total de Retenções (Impostos):  {_formatar_moeda(total_retencoes)}")
    y -= 16
    p.setFont("Helvetica-Bold", 11)
    p.drawString(margin_left, y, f"Valor Líquido a Pagar:          {_formatar_moeda(valor_liquido)}")
    y -= 24

    # --- DADOS BANCÁRIOS DO CREDOR ---
    conta_credor = processo.credor.conta if processo.credor else None
    if conta_credor:
        p.setFont("Helvetica-Bold", 11)
        p.drawString(margin_left, y, "DADOS BANCÁRIOS DO CREDOR:")
        y -= 16
        p.setFont("Helvetica", 11)
        p.drawString(margin_left, y, f"Banco:    {conta_credor.banco or 'Não informado'}")
        y -= 16
        p.drawString(margin_left, y, f"Agência:  {conta_credor.agencia or 'Não informado'}")
        y -= 16
        p.drawString(margin_left, y, f"Conta:    {conta_credor.conta or 'Não informado'}")
        y -= 24

    # --- DETALHAMENTO ---
    p.setFont("Helvetica-Bold", 11)
    p.drawString(margin_left, y, "DETALHAMENTO / JUSTIFICATIVA:")
    y -= 16
    detalhamento = processo.detalhamento or "Não informado."
    y = _draw_wrapped_text(p, detalhamento, margin_left, y, text_width, font_name="Helvetica", font_size=11)
    y -= 20

    # --- BOILERPLATE LEGAL ---
    p.setLineWidth(0.5)
    p.line(margin_left, y, width - margin_right, y)
    y -= 16

    boilerplate = (
        "Autorizo, nos termos da legislação vigente, o pagamento da despesa acima especificada, "
        "face à regular liquidação do processo."
    )
    _draw_wrapped_text(p, boilerplate, margin_left, y, text_width, font_name="Helvetica-Oblique", font_size=10)

    # --- BLOCO DE ASSINATURA ---
    sig_x = width / 2.0
    p.setFont("Helvetica", 10)
    p.drawCentredString(sig_x, _AUTH_SIG_Y + _AUTH_SIG_DATE_OFFSET, "Local e Data: _____________________________, _____ / _____ / _________")
    p.line(sig_x - _AUTH_SIG_HALF_WIDTH, _AUTH_SIG_Y, sig_x + _AUTH_SIG_HALF_WIDTH, _AUTH_SIG_Y)
    p.drawCentredString(sig_x, _AUTH_SIG_Y - 14, "Ordenador(a) de Despesa")

    p.showPage()
    p.save()
    buffer.seek(0)

    return merge_canvas_with_template(buffer, settings.CRECI_LETTERHEAD_PATH)


# Geometry for the PCD signature blocks.
_PCD_SIG_Y = 120
_PCD_SIG_HALF_WIDTH = 130


def gerar_pdf_pcd(diaria):
    """
    Gera o PDF "Proposta de Concessão de Diárias (PCD)" para a diária especificada.
    Inclui numeração, dados do beneficiário, detalhes da viagem e espaço para
    identificação e assinatura do beneficiário.
    Retorna um BytesIO contendo o PDF final mesclado com o papel timbrado.
    """
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_left = 70
    margin_right = 70
    text_width = width - margin_left - margin_right

    y = height - 160

    # --- CABEÇALHO ---
    p.setFont("Helvetica-Bold", 13)
    p.drawCentredString(width / 2.0, y, "PROPOSTA DE CONCESSÃO DE DIÁRIAS (PCD)")
    y -= 18
    p.setFont("Helvetica-Bold", 11)
    p.drawCentredString(width / 2.0, y, f"Nº {diaria.numero_siscac}")
    y -= 16
    p.setFont("Helvetica", 10)
    p.drawCentredString(width / 2.0, y, f"Tipo: {diaria.get_tipo_solicitacao_display()}")
    y -= 28

    p.setLineWidth(0.5)
    p.line(margin_left, y, width - margin_right, y)
    y -= 20

    # --- DADOS DO BENEFICIÁRIO ---
    nome = str(diaria.beneficiario.nome) if diaria.beneficiario and diaria.beneficiario.nome else "Não informado"
    cpf = str(diaria.beneficiario.cpf_cnpj) if diaria.beneficiario and diaria.beneficiario.cpf_cnpj else "Não informado"
    cargo = str(diaria.beneficiario.cargo_funcao) if diaria.beneficiario and diaria.beneficiario.cargo_funcao else "Não informado"

    p.setFont("Helvetica-Bold", 11)
    p.drawString(margin_left, y, "DADOS DO BENEFICIÁRIO:")
    y -= 16
    p.setFont("Helvetica", 11)
    p.drawString(margin_left, y, f"Nome:              {nome}")
    y -= 16
    p.drawString(margin_left, y, f"CPF:               {cpf}")
    y -= 16
    p.drawString(margin_left, y, f"Cargo / Função:    {cargo}")
    y -= 24

    # --- DADOS DO PROPONENTE ---
    if diaria.proponente:
        p.setFont("Helvetica-Bold", 11)
        p.drawString(margin_left, y, "PROPONENTE:")
        y -= 16
        p.setFont("Helvetica", 11)
        nome_p = diaria.proponente.get_full_name() or diaria.proponente.username
        cpf_p = diaria.proponente.email or "Não informado"
        cargo_p = "Não informado"
        p.drawString(margin_left, y, f"Nome:              {nome_p}")
        y -= 16
        p.drawString(margin_left, y, f"CPF:               {cpf_p}")
        y -= 16
        p.drawString(margin_left, y, f"Cargo / Função:    {cargo_p}")
        y -= 24

    # --- DADOS DA VIAGEM ---
    p.setFont("Helvetica-Bold", 11)
    p.drawString(margin_left, y, "DADOS DA VIAGEM:")
    y -= 16
    p.setFont("Helvetica", 11)

    data_saida = diaria.data_saida.strftime('%d/%m/%Y') if diaria.data_saida else "Não informado"
    data_retorno = diaria.data_retorno.strftime('%d/%m/%Y') if diaria.data_retorno else "Não informado"

    p.drawString(margin_left, y, f"Data de Saída:           {data_saida}")
    y -= 16
    p.drawString(margin_left, y, f"Data de Retorno:         {data_retorno}")
    y -= 16
    p.drawString(margin_left, y, f"Cidade de Origem:        {diaria.cidade_origem or 'Não informado'}")
    y -= 16
    p.drawString(margin_left, y, f"Cidade(s) de Destino:    {diaria.cidade_destino or 'Não informado'}")
    y -= 16
    if diaria.meio_de_transporte:
        p.drawString(margin_left, y, f"Meio de Transporte:      {diaria.meio_de_transporte}")
        y -= 16
    y -= 8

    # --- OBJETIVO DA VIAGEM ---
    p.setFont("Helvetica-Bold", 11)
    p.drawString(margin_left, y, "OBJETIVO DA VIAGEM:")
    y -= 16
    y = _draw_wrapped_text(p, diaria.objetivo or "Não informado.", margin_left, y, text_width,
                           font_name="Helvetica", font_size=11)
    y -= 20

    # --- VALORES ---
    p.setFont("Helvetica-Bold", 11)
    p.drawString(margin_left, y, "VALORES:")
    y -= 16
    p.setFont("Helvetica", 11)
    p.drawString(margin_left, y, f"Quantidade de Diárias:   {diaria.quantidade_diarias}")
    y -= 16
    p.setFont("Helvetica-Bold", 11)
    p.drawString(margin_left, y, f"Valor Total:             {_formatar_moeda(diaria.valor_total)}")
    y -= 28

    # --- BOILERPLATE LEGAL ---
    p.setLineWidth(0.5)
    p.line(margin_left, y, width - margin_right, y)
    y -= 14
    boilerplate = (
        "Proposta de concessão de diárias elaborada nos termos da legislação e regulamento interno vigentes, "
        "para fins de autorização pelo Ordenador de Despesas."
    )
    _draw_wrapped_text(p, boilerplate, margin_left, y, text_width, font_name="Helvetica-Oblique", font_size=10)

    # --- BLOCOS DE ASSINATURA ---
    sig_left_x = margin_left + _PCD_SIG_HALF_WIDTH
    sig_right_x = width - margin_right - _PCD_SIG_HALF_WIDTH

    p.setFont("Helvetica", 9)

    # Beneficiário (left) — pre-filled identification
    p.drawCentredString(sig_left_x, _PCD_SIG_Y + 38, nome)
    p.drawCentredString(sig_left_x, _PCD_SIG_Y + 26, f"CPF: {cpf}")
    p.drawCentredString(sig_left_x, _PCD_SIG_Y + 14, cargo)
    p.line(sig_left_x - _PCD_SIG_HALF_WIDTH, _PCD_SIG_Y,
           sig_left_x + _PCD_SIG_HALF_WIDTH, _PCD_SIG_Y)
    p.drawCentredString(sig_left_x, _PCD_SIG_Y - 12, "Assinatura do(a) Beneficiário(a)")

    # Ordenador de Despesa (right)
    p.drawCentredString(sig_right_x, _PCD_SIG_Y + 14,
                        "Local e Data: _____ / _____ / _________")
    p.line(sig_right_x - _PCD_SIG_HALF_WIDTH, _PCD_SIG_Y,
           sig_right_x + _PCD_SIG_HALF_WIDTH, _PCD_SIG_Y)
    p.drawCentredString(sig_right_x, _PCD_SIG_Y - 12, "Ordenador(a) de Despesa")

    p.showPage()
    p.save()
    buffer.seek(0)

    return merge_canvas_with_template(buffer, settings.CRECI_LETTERHEAD_PATH)


def gerar_pdf_conselho_fiscal(processo):
    """
    Gera o PDF "Parecer do Conselho Fiscal" para o processo especificado.
    Inclui integridade documental, trilha de auditoria e contingências.
    Retorna um BytesIO contendo o PDF final mesclado com o papel timbrado.
    """
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_left = 70
    margin_right = 70
    text_width = width - margin_left - margin_right
    # Limite inferior para conteúdo (acima dos blocos de assinatura)
    y_min = _SIGNATURE_BLOCK_HEIGHT

    y = height - 160

    # --- CABEÇALHO ---
    p.setFont("Helvetica-Bold", 13)
    p.drawCentredString(width / 2.0, y, "PARECER DE AUDITORIA - CONSELHO FISCAL")
    y -= 18
    p.setFont("Helvetica-Bold", 11)
    p.drawCentredString(width / 2.0, y, f"PROCESSO Nº {processo.id}")
    y -= 28

    p.setLineWidth(0.5)
    p.line(margin_left, y, width - margin_right, y)
    y -= 18

    # --- INTEGRIDADE DOCUMENTAL ---
    total_docs, total_pages = _contar_paginas_documentos(processo)

    p.setFont("Helvetica-Bold", 11)
    p.drawString(margin_left, y, "INTEGRIDADE DOCUMENTAL:")
    y -= 16

    integridade_texto = (
        f"O processo é composto por {total_docs} documento(s) anexo(s) "
        f"totalizando {total_pages} página(s)."
    )
    y = _draw_wrapped_text(p, integridade_texto, margin_left, y, text_width, font_name="Helvetica", font_size=11)
    y -= 20

    # --- TRILHA DE AUDITORIA ---
    p.setFont("Helvetica-Bold", 11)
    p.drawString(margin_left, y, "TRILHA DE AUDITORIA (TRANSIÇÕES DE STATUS):")
    y -= 16

    history_records = list(processo.history.all().order_by('history_date'))
    log_lines = []
    for i, record in enumerate(history_records):
        prev_status_id = history_records[i - 1].status_id if i > 0 else None
        if record.history_type == '+' or (record.history_type == '~' and record.status_id != prev_status_id):
            try:
                if record.history_user:
                    user_str = record.history_user.get_full_name() or record.history_user.username
                else:
                    user_str = "Sistema"
                date_str = record.history_date.strftime('%d/%m/%Y às %H:%M')
                if record.history_type == '+':
                    log_lines.append(f"• Processo criado em {date_str} por {user_str}")
                else:
                    status_str = str(record.status) if record.status else "Status atualizado"
                    log_lines.append(f"• {status_str} em {date_str} por {user_str}")
            except Exception:
                pass

    if log_lines:
        for line in log_lines[:_MAX_AUDIT_TRAIL_ENTRIES]:
            if y > y_min:
                y = _draw_wrapped_text(
                    p, line, margin_left, y, text_width,
                    font_name="Helvetica", font_size=10, leading=14,
                )
    else:
        p.setFont("Helvetica-Oblique", 10)
        p.drawString(margin_left, y, "Nenhuma transição de status registrada.")
        y -= 14

    y -= 16

    # --- CONTINGÊNCIAS ---
    if y > y_min:
        p.setFont("Helvetica-Bold", 11)
        p.drawString(margin_left, y, "CONTINGÊNCIAS E RETIFICAÇÕES EXCEPCIONAIS:")
        y -= 16

        contingencias = processo.contingencias.all().select_related(
            'solicitante', 'aprovado_por_supervisor', 'aprovado_por_ordenador', 'aprovado_por_conselho'
        )

        if contingencias.exists():
            for cont in contingencias:
                if y <= y_min:
                    break
                solicitante_str = cont.solicitante.get_full_name() or cont.solicitante.username
                data_str = cont.data_solicitacao.strftime('%d/%m/%Y')
                status_display = cont.get_status_display()

                cont_header = (
                    f"• Contingência #{cont.pk} [{status_display}] — "
                    f"Solicitada em {data_str} por {solicitante_str}"
                )
                y = _draw_wrapped_text(
                    p, cont_header, margin_left, y, text_width,
                    font_name="Helvetica-Bold", font_size=10, leading=14,
                )

                if cont.justificativa and y > y_min:
                    y = _draw_wrapped_text(
                        p, f"  Justificativa: {cont.justificativa}",
                        margin_left, y, text_width,
                        font_name="Helvetica", font_size=10, leading=13,
                    )

                if cont.aprovado_por_supervisor and y > y_min:
                    aprov = cont.aprovado_por_supervisor
                    y = _draw_wrapped_text(
                        p, f"  Supervisor: Aprovado por {aprov.get_full_name() or aprov.username}",
                        margin_left, y, text_width,
                        font_name="Helvetica", font_size=10, leading=13,
                    )

                if cont.aprovado_por_ordenador and y > y_min:
                    aprov = cont.aprovado_por_ordenador
                    y = _draw_wrapped_text(
                        p, f"  Ordenador: Aprovado por {aprov.get_full_name() or aprov.username}",
                        margin_left, y, text_width,
                        font_name="Helvetica", font_size=10, leading=13,
                    )

                if cont.aprovado_por_conselho and y > y_min:
                    aprov = cont.aprovado_por_conselho
                    y = _draw_wrapped_text(
                        p, f"  Conselho: Aprovado por {aprov.get_full_name() or aprov.username}",
                        margin_left, y, text_width,
                        font_name="Helvetica", font_size=10, leading=13,
                    )

                y -= 8
        else:
            p.setFont("Helvetica-Bold", 10)
            p.drawString(
                margin_left, y,
                "Nenhuma contingência ou retificação excepcional registrada para este processo.",
            )
            y -= 16

    y -= 10

    # --- BOILERPLATE LEGAL ---
    if y > y_min:
        p.setLineWidth(0.5)
        p.line(margin_left, y, width - margin_right, y)
        y -= 14
        boilerplate = (
            "O Conselho Fiscal manifesta-se pela REGULARIDADE das despesas, "
            "conforme histórico auditado acima."
        )
        _draw_wrapped_text(p, boilerplate, margin_left, y, text_width, font_name="Helvetica-Oblique", font_size=10)

    # --- BLOCOS DE ASSINATURA (3 conselheiros) ---
    positions = [
        (margin_left + _COUNCIL_SIG_WIDTH / 2, "Conselheiro(a) Fiscal 1"),
        (width / 2.0, "Conselheiro(a) Fiscal 2"),
        (width - margin_right - _COUNCIL_SIG_WIDTH / 2, "Conselheiro(a) Fiscal 3"),
    ]
    p.setFont("Helvetica", 9)
    for sig_x, label in positions:
        p.line(sig_x - _COUNCIL_SIG_WIDTH / 2, _COUNCIL_SIG_Y, sig_x + _COUNCIL_SIG_WIDTH / 2, _COUNCIL_SIG_Y)
        p.drawCentredString(sig_x, _COUNCIL_SIG_Y - 12, label)

    p.showPage()
    p.save()
    buffer.seek(0)

    return merge_canvas_with_template(buffer, settings.CRECI_LETTERHEAD_PATH)


def parse_siscac_report(pdf_file):
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


def sync_siscac_payments(extracted_payments):
    from .models import Processo

    resultados = {'sucessos': [], 'divergencias': [], 'nao_encontrados': [], 'retroativos_corrigidos': 0}
    matched_processo_ids = []

    for payment in extracted_payments:
        if payment['comprovante'] is None:
            continue

        candidates = Processo.objects.filter(
            comprovantes_pagamento__numero_comprovante=payment['comprovante'],
            n_nota_empenho=payment['nota_empenho'],
        ).select_related('credor')

        for processo in candidates:
            if processo.credor is None or not processo.credor.nome:
                continue

            credor_nome_upper = processo.credor.nome.upper()
            payment_credor_upper = payment['credor'].upper()
            credor_match = (
                payment_credor_upper in credor_nome_upper or credor_nome_upper in payment_credor_upper
            )

            valor_decimal = payment['valor_total'].quantize(Decimal('0.01'))
            valor_match = (valor_decimal == processo.valor_liquido)

            if credor_match and valor_match:
                if processo.n_pagamento_siscac != payment['siscac_pg']:
                    if processo.n_pagamento_siscac:
                        resultados['retroativos_corrigidos'] += 1
                    processo.n_pagamento_siscac = payment['siscac_pg']
                    processo.save(update_fields=['n_pagamento_siscac'])
                resultados['sucessos'].append({
                    'id': processo.id,
                    'siscac_pg': payment['siscac_pg'],
                    'credor': processo.credor.nome,
                    'valor': processo.valor_liquido,
                })
                matched_processo_ids.append(processo.id)
            else:
                resultados['divergencias'].append({
                    'processo_id': processo.id,
                    'siscac_pg': payment['siscac_pg'],
                    'credor_siscac': payment['credor'],
                    'valor_siscac': valor_decimal,
                    'credor_sistema': processo.credor.nome,
                    'valor_sistema': processo.valor_liquido,
                })
                matched_processo_ids.append(processo.id)

    status_pagos = [
        "PAGO - EM CONFERÊNCIA",
        "PAGO - A CONTABILIZAR",
        "CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL",
        "APROVADO - PENDENTE ARQUIVAMENTO",
        "ARQUIVADO",
    ]
    orphans = Processo.objects.filter(
        status__status_choice__in=status_pagos
    ).filter(
        Q(n_pagamento_siscac__isnull=True) | Q(n_pagamento_siscac__exact='')
    ).exclude(
        id__in=matched_processo_ids
    ).select_related('credor')

    for orphan in orphans:
        resultados['nao_encontrados'].append({
            'id': orphan.id,
            'credor': orphan.credor.nome if orphan.credor else '—',
            'data_pagamento': orphan.data_pagamento,
            'valor_liquido': orphan.valor_liquido,
        })

    return resultados


import csv as _csv_module
from decimal import InvalidOperation


def sync_diarias_siscac_csv(csv_file):
    from .models import Diaria, Credor, StatusChoicesVerbasIndenizatorias

    resultados = {'criadas': 0, 'atualizadas': 0, 'erros': []}

    content = csv_file.read().decode('utf-8')
    reader = _csv_module.reader(io.StringIO(content), delimiter=';')

    # Skip garbage header lines until the actual table header is found
    for line in reader:
        if line and line[0].strip() == 'Número':
            break

    for row in reader:
        # Skip empty rows
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

        # Convert dates
        try:
            saida = datetime.strptime(saida_str, '%d/%m/%Y').date() if saida_str else None
            retorno = datetime.strptime(retorno_str, '%d/%m/%Y').date() if retorno_str else None
        except ValueError:
            resultados['erros'].append(f'Data inválida na linha com Nº {numero_csv}')
            continue

        # Convert currency value
        try:
            valor_diaria = Decimal(valor_str.replace('.', '').replace(',', '.')) if valor_str else None
        except InvalidOperation:
            valor_diaria = None

        # Convert quantity
        try:
            quantidade = Decimal(qtd_str.replace(',', '.')) if qtd_str else Decimal('1')
        except InvalidOperation:
            quantidade = Decimal('1')

        # Find credor
        credor = Credor.objects.filter(nome__icontains=row_name).first()
        if credor is None:
            resultados['erros'].append(f'Credor não encontrado para: {row_name}')
            continue

        # Resolve status FK (use case-insensitive filter to avoid duplicates)
        status_obj = None
        if situacao_str:
            status_obj = StatusChoicesVerbasIndenizatorias.objects.filter(
                status_choice__iexact=situacao_str
            ).first()
            if status_obj is None:
                status_obj = StatusChoicesVerbasIndenizatorias.objects.create(
                    status_choice=situacao_str
                )

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
