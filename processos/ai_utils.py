from google import genai
from google.genai import types
import json
import tempfile
import os
import io
from django.conf import settings
from django.core.files.storage import default_storage
from pypdf import PdfWriter, PdfReader

# Inicializa o novo Client unificado de forma lazy para evitar falha quando a
# chave não está configurada (ex.: ambiente de testes).
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


# Mantém o alias `client` para retrocompatibilidade com o restante do módulo.
class _ClientProxy:
    """Proxy transparente que inicializa o cliente Gemini apenas quando usado."""

    def __getattr__(self, name):
        return getattr(_get_client(), name)


client = _ClientProxy()

def extrair_dados_documento(arquivo_pdf, tipo_documento):
    """
    Motor de extração usando o novo SDK google-genai
    """
    # 1. Salva temporariamente o arquivo que veio da requisição web
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        for chunk in arquivo_pdf.chunks():
            temp_pdf.write(chunk)
        temp_path = temp_pdf.name

    try:
        # 2. Faz o upload usando a nova API de Files
        uploaded_file = client.files.upload(file=temp_path)

        # 3. Define os Schemas conforme o tipo (O seu Dicionário de Dados)
        if tipo_documento == 'DOCUMENTOS ORÇAMENTÁRIOS':
            prompt = """
            Você é um auditor financeiro. Extraia os dados desta Nota de Empenho (NE).
            Retorne APENAS um JSON válido seguindo estritamente estas chaves:
            {
                "n_nota_empenho": "Número do empenho (ex: 2026NE000123)",
                "data_empenho": "Data de emissão no formato YYYY-MM-DD",
                "credor_cnpj": "Apenas os números do CNPJ/CPF do credor favorecido",
                "credor_nome": "Razão social ou nome do credor",
                "valor_bruto": "Valor total do empenho em formato float (ex: 1500.50)",
                "detalhamento": "Resumo ou descrição do objeto/material adquirido"
            }
            """
        elif tipo_documento == 'BOLETO BANCÁRIO':
            prompt = """
            Extraia os dados deste boleto bancário.
            Retorne APENAS um JSON válido seguindo estritamente estas chaves:
            {
                "codigo_barras": "Linha digitável completa (apenas números)",
                "data_vencimento": "Data de vencimento no formato YYYY-MM-DD",
                "valor_liquido": "Valor a pagar em float (ex: 1500.50)",
                "credor_cnpj": "Apenas os números do CNPJ/CPF do beneficiário",
                "credor_nome": "Nome do beneficiário"
            }
            """
        elif tipo_documento == 'NOTA FISCAL (NF)':
            prompt = """
            Extraia os dados desta Nota Fiscal Eletrônica.
            Retorne APENAS um JSON válido seguindo estritamente estas chaves:
            {
                "numero_nota_fiscal": "Número da nota",
                "data_emissao": "Data de emissão no formato YYYY-MM-DD",
                "cnpj_emitente": "Apenas os números do CNPJ do prestador/emitente",
                "nome_emitente": "Razão social do emitente",
                "valor_bruto": "Valor total bruto da nota em formato float",
                "valor_liquido": "Valor líquido a receber em formato float"
            }
            """
        elif tipo_documento == 'ordem_compra':
            prompt = """
            Extraia os dados desta Ordem de Compra ou Serviço.
            Retorne APENAS um JSON válido com estas chaves:
            {
                "n_ordem": "Número da OC/OS",
                "data_emissao": "Formato YYYY-MM-DD",
                "credor_cnpj": "Apenas números do CNPJ do fornecedor",
                "valor_bruto": "Valor total da ordem em float"
            }
            """
        elif tipo_documento == 'liquidacao':
            prompt = """
            Extraia os dados desta Nota de Liquidação/Ateste.
            Retorne APENAS um JSON válido com estas chaves:
            {
                "n_liquidacao": "Número da liquidação",
                "data_pagamento": "Data da liquidação (YYYY-MM-DD)",
                "credor_cnpj": "CNPJ do favorecido",
                "valor_liquido": "Valor liquidado em float",
                "n_nota_empenho": "Número do empenho referenciado",
                "numero_nota_fiscal": "Número da nota fiscal referenciada"
            }
            """
        elif tipo_documento == 'COMPROVANTE DE PAGAMENTO':
            prompt = """
            Você é um auditor financeiro. Extraia os dados deste comprovante de pagamento bancário.
            Retorne APENAS um JSON válido seguindo estritamente estas chaves:
            {
                "credor_nome": "Nome completo do favorecido/destinatário/beneficiário do pagamento",
                "valor_pago": "Valor pago em formato float (ex: 1500.50)",
                "data_pagamento": "Data em que o pagamento foi efetuado no formato YYYY-MM-DD"
            }
            """
        else:
            raise ValueError("Tipo de documento não suportado.")

        # 4. Geração de Conteúdo usando o Novo SDK (Usando o modelo Flash super rápido)
        response = client.models.generate_content(
            model='gemini-2.5-flash', # Pode usar gemini-3.1-flash-lite-preview dependendo da sua cota
            contents=[uploaded_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            print(f"Erro ao converter saída da IA: {response.text}")
            return None

    finally:
        # Garante que o arquivo local é sempre deletado para não lotar o servidor
        if os.path.exists(temp_path):
            os.remove(temp_path)


def extract_data_with_llm(pdf_path):
    """
    Extrai dados fiscais de uma Nota Fiscal usando IA (Gemini).
    Recebe o caminho do arquivo PDF e retorna um dicionário com os campos
    definidos na Etapa 1 do algoritmo de processamento de retenções.
    Retorna None em caso de erro.
    """
    prompt = """
Atue como um auditor fiscal especialista em extração de dados. Analise a nota fiscal
fornecida e retorne ESTRITAMENTE um objeto JSON com as seguintes chaves e formatos.
Não inclua formatação markdown fora do JSON. Valores monetários devem ser números float
(ex: 1500.50). Se um dado não existir, retorne null.

Estrutura exigida:
{
    "valor_bruto": float,
    "valor_liquido": float,
    "optante_simples_nacional": boolean,
    "impostos_federais": {
        "ir": float,
        "pis": float,
        "cofins": float,
        "csll": float
    },
    "justificativa_isencao_federal": string,
    "iss": {
        "valor_destacado": float,
        "local_prestacao_servico": string
    },
    "inss_destacado": float
}
"""
    try:
        uploaded_file = client.files.upload(file=pdf_path)

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[uploaded_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            print(f"Erro ao converter saída da IA (retenções): {response.text}")
            return None

    except Exception as e:
        print(f"Erro na extração de dados fiscais via IA: {e}")
        return None


def extrair_dados_comprovante_ia(pdf_bytes):
    """
    Extrai dados de uma única página de comprovante de pagamento (BytesIO ou caminho).
    Retorna um dict com os campos do modelo ComprovanteDePagamento:
      - credor_nome, valor_pago, data_pagamento
    Retorna None em caso de erro.
    """
    temp_path = None
    try:
        # Aceita tanto BytesIO quanto objetos de arquivo
        if isinstance(pdf_bytes, (bytes, io.BytesIO)):
            content = pdf_bytes if isinstance(pdf_bytes, bytes) else pdf_bytes.read()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(content)
                temp_path = tmp.name
        else:
            # Assume que é um objeto de arquivo Django
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                for chunk in pdf_bytes.chunks():
                    tmp.write(chunk)
                temp_path = tmp.name

        uploaded_file = client.files.upload(file=temp_path)

        prompt = """
        Você é um auditor financeiro. Extraia os dados deste comprovante de pagamento bancário.
        Retorne APENAS um JSON válido seguindo estritamente estas chaves:
        {
            "credor_nome": "Nome completo do favorecido/destinatário/beneficiário do pagamento",
            "valor_pago": "Valor pago em formato float (ex: 1500.50)",
            "data_pagamento": "Data em que o pagamento foi efetuado no formato YYYY-MM-DD"
        }
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[uploaded_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            print(f"Erro ao converter saída da IA (comprovante): {response.text}")
            return None

    except Exception as e:
        print(f"Erro na extração de comprovante via IA: {e}")
        return None

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def extrair_codigos_barras_boletos(caminhos_arquivos):
    """
    Extrai códigos de barras de múltiplos boletos bancários num único envio à IA.
    Mescla os PDFs temporariamente para enviar em uma única chamada ao LLM, evitando
    múltiplas consultas à API.

    Args:
        caminhos_arquivos: lista de strings com caminhos no disco para os PDFs de boleto.

    Returns:
        Lista de strings/None na mesma ordem dos arquivos (None se não encontrado),
        ou None em caso de erro fatal.
    """
    n = len(caminhos_arquivos)
    if n == 0:
        return []

    merged_temp = None

    try:
        writer = PdfWriter()
        page_ranges = []
        current_page = 0

        for caminho in caminhos_arquivos:
            reader = PdfReader(caminho)
            num_pages = len(reader.pages)
            for page in reader.pages:
                writer.add_page(page)
            page_ranges.append((current_page + 1, current_page + num_pages))
            current_page += num_pages

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as merged_file:
            writer.write(merged_file)
            merged_temp = merged_file.name

        page_info = "\n".join(
            f"- Boleto {i + 1}: páginas {start} a {end}"
            for i, (start, end) in enumerate(page_ranges)
        )

        uploaded_file = client.files.upload(file=merged_temp)

        prompt = f"""Este PDF contém {n} boleto(s) bancário(s) concatenado(s).

Distribuição de páginas no PDF:
{page_info}

Para cada boleto, extraia a linha digitável completa (código de barras).
Retorne APENAS um array JSON com exatamente {n} objeto(s), um por boleto, na ordem de aparição:
[
  {{"boleto": 1, "codigo_barras": "somente os dígitos sem espaços ou pontuação"}},
  ...
]
Use null para o campo codigo_barras se não conseguir localizar a linha digitável."""

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[uploaded_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )

        try:
            result = json.loads(response.text)
            if isinstance(result, list):
                return [
                    item.get('codigo_barras') if isinstance(item, dict) else None
                    for item in result
                ]
            return None
        except json.JSONDecodeError:
            print(f"Erro ao converter saída da IA (boletos): {response.text}")
            return None

    except Exception as e:
        print(f"Erro na extração de códigos de barras de boletos: {e}")
        return None

    finally:
        if merged_temp and os.path.exists(merged_temp):
            os.remove(merged_temp)


def processar_pdf_comprovantes_ia(arquivo_pdf):
    """
    Recebe um PDF com um comprovante por página, divide-o e usa IA para extrair
    os dados de cada página conforme o modelo ComprovanteDePagamento.

    Retorna uma lista de dicts com: temp_path, url, pagina, credor_extraido,
    valor_extraido, data_pagamento.
    """
    from .utils import split_pdf_to_temp_pages

    paginas_temp = split_pdf_to_temp_pages(arquivo_pdf)
    resultados = []

    for pagina_info in paginas_temp:
        numero_pagina = pagina_info['pagina']

        # Carrega os bytes da página para passar à IA
        with default_storage.open(pagina_info['temp_path'], 'rb') as f:
            conteudo = f.read()

        # Chama a IA na página isolada
        dados_ia = None
        try:
            dados_ia = extrair_dados_comprovante_ia(conteudo)
        except Exception as e:
            print(f"Erro na extração IA da página {numero_pagina}: {e}")

        resultados.append({
            **pagina_info,
            'credor_extraido': dados_ia.get('credor_nome', 'Não identificado') if dados_ia else 'Não identificado',
            'valor_extraido': dados_ia.get('valor_pago', 0.00) if dados_ia else 0.00,
            'data_pagamento': dados_ia.get('data_pagamento', '') if dados_ia else '',
        })

    return resultados