from google import genai
from google.genai import types
import json
import tempfile
import os
import io
from django.conf import settings

# Inicializa o novo Client unificado
# Se a variável GEMINI_API_KEY estiver definida nas suas variáveis de ambiente,
# o Client() vai encontrá-la automaticamente. Se não, passe-a explicitamente:
client = genai.Client(api_key=settings.GEMINI_API_KEY)

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
                "tipo_de_pagamento": "Classifique o tipo de pagamento como uma das seguintes opções EXATAS: 'GERENCIADOR' (para boleto bancário ou gerenciador financeiro), 'TED' (para transferência TED/DOC), 'PIX' (para pagamento PIX), 'REMESSA' (para remessa bancária). Use apenas esses valores.",
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


def extrair_dados_comprovante_ia(pdf_bytes):
    """
    Extrai dados de uma única página de comprovante de pagamento (BytesIO ou caminho).
    Retorna um dict com os campos do modelo ComprovanteDePagamento:
      - credor_nome, valor_pago, tipo_de_pagamento, data_pagamento
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
            "tipo_de_pagamento": "Classifique o tipo de pagamento como uma das seguintes opções EXATAS: 'GERENCIADOR' (para boleto bancário ou gerenciador financeiro), 'TED' (para transferência TED/DOC), 'PIX' (para pagamento PIX), 'REMESSA' (para remessa bancária). Use apenas esses valores.",
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