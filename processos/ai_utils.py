import io
import os
import json
import PyPDF2
import tempfile
from google import genai
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

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


def processar_pdf_comprovantes_ia(arquivo_upload):
    """
    Envia o PDF completo para a IA extrair Credor e Valor por página.
    Em seguida, usa o PyPDF2 para fatiar fisicamente as páginas e preparar o retorno para o sistema.
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # 1. Salva o arquivo temporariamente no HD para enviar ao Google
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        for chunk in arquivo_upload.chunks():
            temp_file.write(chunk)
        temp_path_full = temp_file.name

    try:
        # 2. Faz o upload para o Gemini
        arquivo_gemini = client.files.upload(file=temp_path_full)

        # 3. O Prompt Blindado focado em arrays
        prompt_sistema = """
        Você é um robô financeiro especialista em extração de dados.
        O documento anexo é um PDF contendo um ou vários comprovantes de pagamento bancário (extratos, transferências, boletos, convênios).
        Cada comprovante está em uma página diferente.

        Sua tarefa:
        Para CADA PÁGINA do documento, identifique:
        1. O nome do Credor / Favorecido. (Procure por "Favorecido", "Destinatário", "Nome", "Transferido para", "Convenio" ou Instituição recebedora). Limpe CNPJs ou descrições inúteis do nome.
        2. O Valor Pago. (Procure por "Valor Total", "Valor do Documento", "Valor Cobrado", "Valor Pago").

        REGRA DE SAÍDA OBRIGATÓRIA:
        Retorne EXATAMENTE E APENAS um array de objetos JSON. Nenhuma palavra a mais, sem formatação markdown no início ou fim.
        Exemplo:
        [
            {"pagina": 1, "credor": "NOME DO CREDOR AQUI", "valor": 1500.50},
            {"pagina": 2, "credor": "OUTRO CREDOR", "valor": 230.00}
        ]
        Se uma página não for um comprovante, retorne credor como "Não identificado" e valor 0.0.
        """

        print("\n🤖 Enviando PDF de comprovantes para o Gemini...")

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[arquivo_gemini, prompt_sistema]
        )

        texto_resposta = response.text.strip()
        print(f"📥 Resposta da IA:\n{texto_resposta}\n")

        # Limpeza do Markdown caso a IA retorne com ```json
        if texto_resposta.startswith("```json"):
            texto_resposta = texto_resposta.replace("```json", "", 1)
        if texto_resposta.endswith("```"):
            texto_resposta = texto_resposta[::-1].replace("```", "", 1)[::-1]

        # Converte a resposta textual da IA em uma lista de Dicionários Python
        dados_ia = json.loads(texto_resposta.strip())

        # Cria um mapa fácil de buscar: {1: {'credor': 'X', 'valor': 10}, 2: ...}
        mapa_ia = {item['pagina']: item for item in dados_ia if isinstance(item, dict) and 'pagina' in item}

        # 4. Fatiamento físico do PDF (para o usuário poder clicar em "Ver Arquivo" no front-end)
        resultados_finais = []
        arquivo_upload.seek(0)
        pdf_reader = PyPDF2.PdfReader(arquivo_upload)

        for i in range(len(pdf_reader.pages)):
            num_pagina = i + 1

            # Busca o que a IA leu para esta página (ou valores zerados se a IA pulou)
            dados_pagina = mapa_ia.get(num_pagina, {"credor": "Não identificado pela IA", "valor": 0.0})

            # Corta a página
            writer = PyPDF2.PdfWriter()
            writer.add_page(pdf_reader.pages[i])

            temp_filename = f"temp/comprovante_pag_{num_pagina}_{arquivo_upload.name}"
            temp_pdf = io.BytesIO()
            writer.write(temp_pdf)

            if default_storage.exists(temp_filename):
                default_storage.delete(temp_filename)

            path = default_storage.save(temp_filename, ContentFile(temp_pdf.getvalue()))

            # 5. Empacota tudo no formato exato que o seu Javascript já espera
            resultados_finais.append({
                'temp_path': path,
                'pagina': num_pagina,
                'credor_extraido': str(dados_pagina.get('credor', 'Não identificado')).upper(),
                'valor_extraido': float(dados_pagina.get('valor', 0.0)),
                'url': default_storage.url(path)
            })

        return resultados_finais

    except Exception as e:
        print(f"Erro na extração IA de comprovantes: {e}")
        raise e
    finally:
        # Faxina obrigatória dos arquivos no disco e no servidor do Google
        if os.path.exists(temp_path_full):
            os.remove(temp_path_full)
        try:
            if 'arquivo_gemini' in locals():
                client.files.delete(name=arquivo_gemini.name)
        except:
            pass