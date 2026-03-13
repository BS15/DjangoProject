import io
import pdfplumber
import PyPDF2
import re
import uuid
from collections import Counter
from pypdf import PdfWriter, PdfReader
from datetime import datetime, timedelta
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
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

def extrair_linha_digitavel(texto):
    """Procura no texto qualquer bloco grande de números e devolve a linha limpa."""
    # Busca qualquer sequência que contenha pelo menos 47 números
    # (podendo estar separados por espaços, pontos ou hifens)
    blocos = re.findall(r'(?:[0-9][\s\.\-]*){47,}', texto)

    for bloco in blocos:
        # Tira tudo que não é número
        numeros = re.sub(r'\D', '', bloco)

        # Regra 1: É conta de consumo (Luz, Água, Telefone)? Tem 48 dígitos e começa com '8'.
        if len(numeros) == 48 and numeros.startswith('8'):
            return numeros, 'arrecadacao'

        # Regra 2: É boleto bancário? Pegamos apenas os últimos 47 dígitos
        # (isso limpa casos como o Bradesco que bota o '237-2' na frente)
        elif len(numeros) >= 47:
            return numeros[-47:], 'bancario'

    return None, None

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
    resultados = []

    pdf_writer_source = PyPDF2.PdfReader(pdf_file)
    pdf_file.seek(0)

    with pdfplumber.open(pdf_file) as pdf_leitor:
        for i, page in enumerate(pdf_leitor.pages):
            texto = page.extract_text() or ""

            # A MÁGICA: Transforma todo o texto da página (com tabelas e colunas) em uma única linha reta
            texto_flat = re.sub(r'\s+', ' ', texto)

            # --- PARTE A: EXTRAÇÃO DO VALOR ---
            # Busca as palavras-chave, ignora símbolos perdidos no meio, e captura o padrão "1.500,00"
            match_valor = re.search(
                r'(?:VALOR TOTAL|VALOR DO DOCUMENTO|VALOR COBRADO|Valor Total|Valor em Dinheiro)[\s\:\-\.]*([\d]{1,3}(?:\.\d{3})*,\d{2})',
                texto_flat,
                re.IGNORECASE
            )

            valor_float = 0.00
            if match_valor:
                valor_str = match_valor.group(1).replace('.', '').replace(',', '.')
                try:
                    valor_float = float(valor_str)
                except ValueError:
                    pass

            # --- PARTE B: EXTRAÇÃO DO CREDOR ---
            credor = "Não identificado automaticamente"

            # Regra 1: Transferência (Procura "TRANSFERIDO PARA: CLIENTE:" e para no próximo campo)
            match_transf = re.search(
                r'TRANSFERIDO PARA:\s*CLIENTE:\s*([A-ZÀ-Ÿ\s\.\-\&]+?)(?:AGENCIA|NR\. DOCUMENTO|CONTA|$)', texto_flat,
                re.IGNORECASE)

            # Regra 2: Convênios (Procura "Convenio" e para em "Codigo de Barras")
            match_convenio = re.search(r'Convenio\s+([A-ZÀ-Ÿ\s\.\-\&]+?)\s*Codigo de Barras', texto_flat, re.IGNORECASE)

            # Regra 3: Títulos/Boletos (Pega o nome da Instituição (Banco X ou S.A.) antes da gigante linha digitável)
            match_banco = re.search(
                r'((?:BANCO|CAIXA)[A-ZÀ-Ÿ\s\.\-\&]+?|[A-ZÀ-Ÿ\s\.\-\&]+?S\/?\.?A\.?)\s*(?:\d[\s\.\-]*){47,55}',
                texto_flat, re.IGNORECASE)

            # Regra 4: Termos genéricos (Favorecido, Destinatário, Recebedor)
            match_fav = re.search(
                r'(?:Favorecido|Nome|Credor|Destinat[áa]rio|Recebedor|CLIENTE)[\s:]+([A-ZÀ-Ÿ\s\.\-\&]{5,40}?)(?:AGENCIA|DATA|CONTA|CNPJ|CPF|$)',
                texto_flat, re.IGNORECASE)

            # Aplica a primeira regra que der match
            if match_transf:
                credor = match_transf.group(1).strip()
            elif match_convenio:
                credor = match_convenio.group(1).strip()
            elif match_banco:
                credor = match_banco.group(1).strip()
            elif match_fav:
                credor = match_fav.group(1).strip()

            # Remove lixos comuns do final da string
            credor = re.sub(r'(?:SISTEMA|SISBB|AUTOATENDIMENTO).*', '', credor, flags=re.IGNORECASE).strip()

            # --- PARTE C: FATIAMENTO E SALVAMENTO ---
            writer = PyPDF2.PdfWriter()
            pypdf_page = pdf_writer_source.pages[i]
            writer.add_page(pypdf_page)

            temp_filename = f"temp/comprovante_pag_{i + 1}_{pdf_file.name}"
            temp_pdf = io.BytesIO()
            writer.write(temp_pdf)

            if default_storage.exists(temp_filename):
                default_storage.delete(temp_filename)

            path = default_storage.save(temp_filename, ContentFile(temp_pdf.getvalue()))

            # --- PARTE D: EMPACOTAMENTO ---
            resultados.append({
                'temp_path': path,
                'pagina': i + 1,
                'credor_extraido': credor,
                'valor_extraido': valor_float,
                'url': default_storage.url(path)
            })
    print(resultados)
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

def fatiar_pdf_manual(arquivo_pdf):
    """
    Recebe um PDF, divide-o página a página e guarda ficheiros temporários.
    Retorna uma lista de caminhos temporários.
    """
    pdf = PdfReader(arquivo_pdf)
    caminhos_temporarios = []

    for numero_pagina in range(len(pdf.pages)):
        writer = PdfWriter()
        writer.add_page(pdf.pages[numero_pagina])

        buffer = io.BytesIO()
        writer.write(buffer)
        buffer.seek(0)

        # Gera um nome único para evitar colisões
        nome_temp = f"temp_comprovante_{uuid.uuid4().hex[:8]}_pag{numero_pagina+1}.pdf"
        caminho_salvo = default_storage.save(f"temp/{nome_temp}", ContentFile(buffer.read()))

        caminhos_temporarios.append({
            'temp_path': caminho_salvo,
            'url': default_storage.url(caminho_salvo), # Para o utilizador poder visualizar
            'pagina': numero_pagina + 1
        })

    return caminhos_temporarios


def processar_pdf_comprovantes_ia(arquivo_pdf):
    """
    Recebe um PDF com um comprovante por página, divide-o e usa IA para extrair
    os dados de cada página conforme o modelo ComprovanteDePagamento.
    Retorna uma lista de dicts com: temp_path, url, pagina, credor_extraido,
    valor_extraido, tipo_de_pagamento, data_pagamento.
    """
    from .ai_utils import extrair_dados_comprovante_ia

    resultados = []
    pdf = PdfReader(arquivo_pdf)

    for numero_pagina in range(len(pdf.pages)):
        # 1. Fatia a página individual
        writer = PdfWriter()
        writer.add_page(pdf.pages[numero_pagina])

        buffer = io.BytesIO()
        writer.write(buffer)
        buffer.seek(0)

        # 2. Salva o arquivo temporário
        nome_temp = f"temp_comprovante_{uuid.uuid4().hex[:8]}_pag{numero_pagina+1}.pdf"
        conteudo = buffer.read()
        caminho_salvo = default_storage.save(f"temp/{nome_temp}", ContentFile(conteudo))

        # 3. Chama a IA na página isolada
        dados_ia = None
        try:
            dados_ia = extrair_dados_comprovante_ia(conteudo)
        except Exception as e:
            print(f"Erro na extração IA da página {numero_pagina + 1}: {e}")

        resultado = {
            'temp_path': caminho_salvo,
            'url': default_storage.url(caminho_salvo),
            'pagina': numero_pagina + 1,
            'credor_extraido': dados_ia.get('credor_nome', 'Não identificado') if dados_ia else 'Não identificado',
            'valor_extraido': dados_ia.get('valor_pago', 0.00) if dados_ia else 0.00,
            'tipo_de_pagamento': dados_ia.get('tipo_de_pagamento', '') if dados_ia else '',
            'data_pagamento': dados_ia.get('data_pagamento', '') if dados_ia else '',
        }
        resultados.append(resultado)

    return resultados