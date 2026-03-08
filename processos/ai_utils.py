import os
import json
import tempfile
from google import genai
from django.conf import settings

# Configuração da API (certifique-se de ter GEMINI_API_KEY no seu settings.py ou .env)

def gerar_esquema_para_ia(modelo_django):
    """
    Gera um esquema dividido em duas partes: dados gerais da nota e lista de impostos.
    """
    esquema_geral = {}

    campos_ignorados = ['id', 'processo', 'dados_extraidos', 'arquivo_pdf', 'nota_fiscal', 'codigo']

    # 1. Monta a gaveta de Dados Gerais baseada no seu Banco de Dados
    for campo in modelo_django._meta.fields:
        if campo.name not in campos_ignorados:
            esquema_geral[campo.name] = str(campo.verbose_name).title()

    # 2. Prepara a estrutura final separada
    esquema_final = {
        "dados_gerais": esquema_geral
    }

    # 3. Se for uma Nota Fiscal, adicionamos a gaveta de Impostos isolada
    if modelo_django.__name__ == 'NotaFiscal':
        # Pede para a IA extrair também o texto bruto das observações para o funcionário ler
        esquema_geral[
            'texto_observacoes'] = "Copie o texto integral do campo de Observações, Informações Complementares ou Dados Adicionais."

        # Cria a segunda gaveta exclusiva para a tributação
        esquema_final['impostos'] = [
            {
                "imposto": "Sigla do imposto (ex: IR, CSLL, COFINS, PIS, INSS, ISS). ATENÇÃO: Procure de forma minuciosa dentro do campo de observações e dados adicionais.",
                "valor": "Valor numérico retido (ex: 150.00)"
            }
        ]

    return esquema_final


def extrair_dados_documento(arquivo_upload, modelo_django):
    """
    Recebe um arquivo (request.FILES) e a classe do Model.
    Retorna um dicionário com as chaves exatas do Model e os valores encontrados.
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    # 1. Gera o esquema dinâmico com base no Model recebido
    esquema_esperado = gerar_esquema_para_ia(modelo_django)
    formato_json_exigido = json.dumps(esquema_esperado, indent=2, ensure_ascii=False)

    # Cria um arquivo temporário seguro (funciona no Linux e no Windows)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        for chunk in arquivo_upload.chunks():
            temp_file.write(chunk)
        temp_path = temp_file.name

    try:
        # 2. Envia para o servidor do Gemini (NOVA SINTAXE .files)
        arquivo_gemini = client.files.upload(file=temp_path)

        # 3. O PROMPT BLINDADO
        prompt_sistema = f"""
            Você é um robô de extração de dados estritamente técnico.
            Leia o documento em anexo e extraia as informações solicitadas.

            REGRA ABSOLUTA DE SAÍDA:
            Você DEVE retornar APENAS um objeto JSON válido, contendo EXATAMENTE duas chaves principais: "dados_gerais" e "impostos" (se aplicável).
            As CHAVES do JSON devem ser EXATAMENTE as listadas abaixo, sem alterações.
            Os VALORES representam a descrição do que você deve procurar no documento.
            
            1. Os impostos podem estar destacados nos seus respectivos campos ou podem estar descritos no campo "Observações" ou "Informações Complementares" (ex: "Retenção de PIS R$ 10,00, COFINS R$ 30,00"). Leia este campo com extrema atenção. Caso o valor relacionado à determinado imposto seja nulo, desconsidere e NÃO o inclua no arquivo json.
            
            Se você não encontrar a informação exata, o valor da chave deve ser estritamente null.
            Valores monetários devem conter apenas números e ponto (ex: 1500.50).
            Datas devem vir no formato DD-MM-YYYY.

            ESTRUTURA OBRIGATÓRIA QUE VOCÊ DEVE DEVOLVER:
            {formato_json_exigido}
            """
        # --- NOVIDADE: PRINT DO PROMPT ---
        print("\n" + "=" * 60)
        print("🤖 [DEBUG IA] - PROMPT ENVIADO:")
        print("=" * 60)
        print(prompt_sistema)
        print("Enviando arquivo PDF para o Google Gemini...\n")
        # 4. GERAÇÃO DE CONTEÚDO (NOVA SINTAXE .models)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[arquivo_gemini, prompt_sistema]
        )

        # 5. Limpeza dupla de segurança (texto puro -> JSON -> Dicionário Python)
        texto_resposta = response.text.strip()

        # --- NOVIDADE: PRINT DA RESPOSTA CRUA ---
        print("\n" + "=" * 60)
        print("📥 [DEBUG IA] - RESPOSTA CRUA RECEBIDA:")
        print("=" * 60)
        print(texto_resposta)
        print("=" * 60 + "\n")

        if texto_resposta.startswith("```json"):
            texto_resposta = texto_resposta.replace("```json", "", 1)
        if texto_resposta.endswith("```"):
            texto_resposta = texto_resposta[::-1].replace("```", "", 1)[::-1]

        dados_json = json.loads(texto_resposta.strip())
        return dados_json

    except json.JSONDecodeError as e:
        print(f"Erro na conversão do JSON: {e} - Retorno bruto: {texto_resposta}")
        return None
    except Exception as e:
        print(f"Erro inesperado na API: {e}")
        return None
    finally:
        # 6. Faxina garantida
        if os.path.exists(temp_path):
            os.remove(temp_path)
        try:
            # NOVA SINTAXE para deletar o arquivo lá no servidor do Google
            if 'arquivo_gemini' in locals():
                client.files.delete(name=arquivo_gemini.name)
        except Exception as e:
            print(f"Aviso: Não conseguiu deletar o arquivo remoto: {e}")
            pass