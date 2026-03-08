import io
import pdfplumber
import PyPDF2
import re
from collections import Counter
from pypdf import PdfWriter
from datetime import datetime, timedelta
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

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
    """
    Lê um PDF multicamadas (ex: extrato de pagamentos do banco), separa página por página,
    tenta extrair o Valor e o Credor usando pdfplumber (melhor leitura) e salva as fatias
    temporárias no disco usando PyPDF2 (melhor manipulação).
    """
    resultados = []

    # 1. Abre o PDF usando PyPDF2 apenas para fatiar e salvar
    pdf_writer_source = PyPDF2.PdfReader(pdf_file)

    # 2. Abre o MESMO arquivo usando pdfplumber para extração de texto de alta precisão
    # (Como o arquivo do Django (request.FILES) já foi lido pelo PyPDF2,
    # precisamos voltar o "cursor" da memória dele pro começo)
    pdf_file.seek(0)

    with pdfplumber.open(pdf_file) as pdf_leitor:

        for i, page in enumerate(pdf_leitor.pages):
            # --- PARTE A: EXTRAÇÃO DE DADOS (pdfplumber) ---
            texto = page.extract_text() or ""

            # Limpa quebras de linha múltiplas para facilitar o Regex
            texto_limpo = re.sub(r'\s+', ' ', texto)

            # Tenta achar o Valor (Busca "Valor:", "Valor Pago:", "R$", etc. seguido de números)
            # Regex: Procura palavras chave, ignora espaços/símbolos soltos, e captura o padrão "1.500,00" ou "1500,00"
            match_valor = re.search(r'(?:Valor|Pago|R\$|Documento)[\s:\-\.]*([\d]{1,3}(?:\.\d{3})*,\d{2})', texto_limpo,
                                    re.IGNORECASE)

            valor_float = 0.00
            if match_valor:
                # Transforma "1.500,00" em "1500.00" para o Python converter pra float
                valor_str = match_valor.group(1).replace('.', '').replace(',', '.')
                try:
                    valor_float = float(valor_str)
                except ValueError:
                    pass

            # Tenta achar o Credor (Busca "Favorecido", "Nome", "Destinatário", "Recebedor")
            # Regex: Pega as palavras chaves e captura até 50 caracteres (letras, espaços, & e -) após elas
            match_credor = re.search(
                r'(?:Favorecido|Nome|Credor|Destinat[áa]rio|Recebedor)[\s:]+([A-ZÀ-Ÿ\s\.\-\&]{5,50})', texto_limpo,
                re.IGNORECASE)

            credor = "Não identificado automaticamente"
            if match_credor:
                credor = match_credor.group(1).strip()
                # Limpa sujeiras comuns do fim da string capturada (ex: se o banco colocou um "CNPJ:" colado no nome)
                credor = re.split(r'(CNPJ|CPF|\d{2}\.)', credor)[0].strip()

            # --- PARTE B: FATIAMENTO E SALVAMENTO (PyPDF2) ---
            writer = PyPDF2.PdfWriter()
            # Pega a página equivalente no PyPDF2 (já que estamos no loop do pdfplumber)
            pypdf_page = pdf_writer_source.pages[i]
            writer.add_page(pypdf_page)

            temp_filename = f"temp/comprovante_pag_{i + 1}_{pdf_file.name}"
            temp_pdf = io.BytesIO()
            writer.write(temp_pdf)

            if default_storage.exists(temp_filename):
                default_storage.delete(temp_filename)

            path = default_storage.save(temp_filename, ContentFile(temp_pdf.getvalue()))

            # --- PARTE C: EMPACOTAMENTO DOS DADOS ---
            resultados.append({
                'temp_path': path,
                'pagina': i + 1,
                'credor_extraido': credor,
                'valor_extraido': valor_float,
                'url': default_storage.url(path)
            })

    return resultados