"""Utilitários transversais para PDF, extração determinística e sincronização SISCAC."""

import io
import os
import pdfplumber
import PyPDF2
import re
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
    """Divide ``line`` por ``keyword`` e devolve a parte desejada com ``strip`` seguro."""
    parts = line.split(keyword)
    if len(parts) > index:
        return parts[index].strip()
    return ""

def parse_br_date(date_str):
    """Converte data brasileira ``DD/MM/AAAA`` para ``AAAA-MM-DD``."""
    try:
        if not date_str: return None
        return datetime.strptime(date_str.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None

def extract_text_between(full_text, start_anchor, end_anchor):
    """Extrai texto entre âncoras, com fallback para quebra de linha."""
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

def extract_siscac_data(pdf_file):
    """Extrai campos básicos de empenho, liquidação e pagamento de PDF SISCAC."""

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
    """Localiza linha digitável de boleto/arrecadação em PDF e retorna payload normalizado."""
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
    """Fatia comprovantes em páginas e extrai credor, valor, data e autenticação por regex."""
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


def sync_siscac_payments(extracted_payments):
    """Concilia pagamentos extraídos com processos internos e classifica sucessos/divergências."""
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
    """Importa/atualiza diárias a partir de CSV SISCAC padronizado por ponto e vírgula."""
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


def preview_diarias_lote(csv_file):
    """Parse and validate a CSV of diárias without inserting anything.

    Returns a dict with:
        'preview'  – list of dicts with validated row data (safe for JSON serialisation)
        'erros'    – list of error strings
    """
    import csv
    import io
    from datetime import datetime
    from decimal import Decimal, InvalidOperation
    from .models import Credor

    resultado = {'preview': [], 'erros': []}

    try:
        conteudo = io.StringIO(csv_file.read().decode('utf-8'))
    except UnicodeDecodeError:
        resultado['erros'].append("Erro de codificação: verifique se o arquivo está salvo em UTF-8.")
        return resultado

    reader = csv.DictReader(conteudo)

    colunas_requeridas = {
        'NOME_BENEFICIARIO', 'DATA_SAIDA', 'DATA_RETORNO',
        'CIDADE_ORIGEM', 'CIDADE_DESTINO', 'OBJETIVO', 'QUANTIDADE_DIARIAS',
    }
    if reader.fieldnames is None or not colunas_requeridas.issubset(set(reader.fieldnames)):
        faltando = colunas_requeridas - set(reader.fieldnames or [])
        resultado['erros'].append(
            f"Cabeçalho inválido. Colunas ausentes: {', '.join(sorted(faltando))}."
        )
        return resultado

    for row in reader:
        nome_planilha = row.get('NOME_BENEFICIARIO', '').strip()

        credor = Credor.objects.filter(nome__iexact=nome_planilha, tipo='PF').first()
        if credor is None:
            credor = Credor.objects.filter(nome__icontains=nome_planilha, tipo='PF').first()
        if credor is None:
            resultado['erros'].append(
                f"Linha {reader.line_num}: Beneficiário com nome '{nome_planilha}' não encontrado no sistema."
            )
            continue

        try:
            data_saida_parsed = datetime.strptime(row['DATA_SAIDA'].strip(), '%d/%m/%Y').date()
            data_retorno_parsed = datetime.strptime(row['DATA_RETORNO'].strip(), '%d/%m/%Y').date()
        except ValueError:
            resultado['erros'].append(
                f"Linha {reader.line_num}: Data inválida. Use o formato DD/MM/AAAA."
            )
            continue

        if data_retorno_parsed < data_saida_parsed:
            resultado['erros'].append(
                f"Linha {reader.line_num}: Data de retorno ({row['DATA_RETORNO'].strip()}) "
                f"não pode ser anterior à data de saída ({row['DATA_SAIDA'].strip()})."
            )
            continue

        try:
            qtd_diarias = Decimal(row['QUANTIDADE_DIARIAS'].strip().replace(',', '.'))
        except InvalidOperation:
            resultado['erros'].append(
                f"Linha {reader.line_num}: Quantidade de diárias inválida: {row['QUANTIDADE_DIARIAS']}."
            )
            continue

        if qtd_diarias <= 0:
            resultado['erros'].append(
                f"Linha {reader.line_num}: Quantidade de diárias deve ser maior que zero."
            )
            continue

        resultado['preview'].append({
            'beneficiario_id': credor.pk,
            'beneficiario_nome': credor.nome,
            'data_saida': data_saida_parsed.strftime('%Y-%m-%d'),
            'data_retorno': data_retorno_parsed.strftime('%Y-%m-%d'),
            'data_saida_display': data_saida_parsed.strftime('%d/%m/%Y'),
            'data_retorno_display': data_retorno_parsed.strftime('%d/%m/%Y'),
            'cidade_origem': row['CIDADE_ORIGEM'].strip(),
            'cidade_destino': row['CIDADE_DESTINO'].strip(),
            'objetivo': row['OBJETIVO'].strip(),
            'quantidade_diarias': str(qtd_diarias),
        })

    return resultado


def importar_diarias_lote(csv_file, usuario_logado):
    import csv
    import io
    from datetime import datetime
    from decimal import Decimal, InvalidOperation
    from .models import Diaria, Credor

    resultados = {'sucessos': 0, 'erros': []}

    try:
        conteudo = io.StringIO(csv_file.read().decode('utf-8'))
    except UnicodeDecodeError:
        resultados['erros'].append("Erro de codificação: verifique se o arquivo está salvo em UTF-8.")
        return resultados

    reader = csv.DictReader(conteudo)

    colunas_requeridas = {
        'NOME_BENEFICIARIO', 'DATA_SAIDA', 'DATA_RETORNO',
        'CIDADE_ORIGEM', 'CIDADE_DESTINO', 'OBJETIVO', 'QUANTIDADE_DIARIAS',
    }
    if reader.fieldnames is None or not colunas_requeridas.issubset(set(reader.fieldnames)):
        faltando = colunas_requeridas - set(reader.fieldnames or [])
        resultados['erros'].append(
            f"Cabeçalho inválido. Colunas ausentes: {', '.join(sorted(faltando))}."
        )
        return resultados

    for row in reader:
        nome_planilha = row.get('NOME_BENEFICIARIO', '').strip()

        credor = Credor.objects.filter(nome__iexact=nome_planilha, tipo='PF').first()
        if credor is None:
            credor = Credor.objects.filter(nome__icontains=nome_planilha, tipo='PF').first()
        if credor is None:
            resultados['erros'].append(
                f"Linha {reader.line_num}: Beneficiário com nome '{nome_planilha}' não encontrado no sistema."
            )
            continue

        try:
            data_saida_parsed = datetime.strptime(row['DATA_SAIDA'].strip(), '%d/%m/%Y').date()
            data_retorno_parsed = datetime.strptime(row['DATA_RETORNO'].strip(), '%d/%m/%Y').date()
        except ValueError:
            resultados['erros'].append(
                f"Linha {reader.line_num}: Data inválida. Use o formato DD/MM/AAAA."
            )
            continue

        if data_retorno_parsed < data_saida_parsed:
            resultados['erros'].append(
                f"Linha {reader.line_num}: Data de retorno ({row['DATA_RETORNO'].strip()}) "
                f"não pode ser anterior à data de saída ({row['DATA_SAIDA'].strip()})."
            )
            continue

        try:
            qtd_diarias = Decimal(row['QUANTIDADE_DIARIAS'].strip().replace(',', '.'))
        except InvalidOperation:
            resultados['erros'].append(
                f"Linha {reader.line_num}: Quantidade de diárias inválida: {row['QUANTIDADE_DIARIAS']}."
            )
            continue

        if qtd_diarias <= 0:
            resultados['erros'].append(
                f"Linha {reader.line_num}: Quantidade de diárias deve ser maior que zero."
            )
            continue

        nova_diaria = Diaria.objects.create(
            beneficiario=credor,
            proponente=usuario_logado,
            data_saida=data_saida_parsed,
            data_retorno=data_retorno_parsed,
            cidade_origem=row['CIDADE_ORIGEM'].strip(),
            cidade_destino=row['CIDADE_DESTINO'].strip(),
            objetivo=row['OBJETIVO'].strip(),
            quantidade_diarias=qtd_diarias,
            autorizada=False,
        )
        nova_diaria.avancar_status('SOLICITADA')
        resultados['sucessos'] += 1

    return resultados


def confirmar_diarias_lote(preview_items, usuario_logado):
    """Insert Diaria records from a list of validated preview dicts.

    Each dict in *preview_items* is the format returned by :func:`preview_diarias_lote`.
    Returns a dict with 'sucessos' (int) and 'erros' (list of str).
    """
    from decimal import Decimal
    from datetime import datetime
    from .models import Diaria, Credor

    resultados = {'sucessos': 0, 'erros': []}

    for item in preview_items:
        credor = Credor.objects.filter(pk=item['beneficiario_id'], tipo='PF').first()
        if credor is None:
            resultados['erros'].append(
                f"Beneficiário com ID {item['beneficiario_id']} não encontrado ao confirmar."
            )
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
            from .pdf_engine import gerar_documento_pdf
            from .models.fluxo import AssinaturaAutentique
            from django.contrib.contenttypes.models import ContentType
            from django.core.files.base import ContentFile
            pdf_bytes = gerar_documento_pdf('scd', nova_diaria)
            assinatura = AssinaturaAutentique(
                content_type=ContentType.objects.get_for_model(nova_diaria),
                object_id=nova_diaria.id,
                tipo_documento='SCD',
                criador=usuario_logado,
                status='RASCUNHO',
            )
            assinatura.arquivo.save(
                f"SCD_{nova_diaria.id}.pdf",
                ContentFile(pdf_bytes),
                save=True,
            )
        except Exception as e:
            resultados['erros'].append(
                f"Diária {nova_diaria.numero_siscac or nova_diaria.id}: SCD não gerado ({e})"
            )

        resultados['sucessos'] += 1

    return resultados
