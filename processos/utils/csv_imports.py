"""CSV parsing and batch import utilities for Verbas Indenizatórias.

The DRY fix: _parse_diaria_row is a single shared validator used by both
the preview and the direct import flows, eliminating ~90% duplication.
"""

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.db.models import Max


def _parse_diaria_row(row, line_num):
    """Valida uma única linha de Diária. Retorna (dict_válido, msg_erro)."""
    from processos.models import Credor

    nome = row.get('NOME_BENEFICIARIO', '').strip()
    credor = (
        Credor.objects.filter(nome__iexact=nome, tipo='PF').first()
        or Credor.objects.filter(nome__icontains=nome, tipo='PF').first()
    )

    if not credor:
        return None, f"Linha {line_num}: Beneficiário '{nome}' não encontrado no sistema."

    try:
        data_saida = datetime.strptime(row['DATA_SAIDA'].strip(), '%d/%m/%Y').date()
        data_retorno = datetime.strptime(row['DATA_RETORNO'].strip(), '%d/%m/%Y').date()
    except ValueError:
        return None, f"Linha {line_num}: Data inválida. Use o formato DD/MM/AAAA."

    if data_retorno < data_saida:
        return (
            None,
            f"Linha {line_num}: Data de retorno ({row['DATA_RETORNO'].strip()}) "
            f"não pode ser anterior à data de saída ({row['DATA_SAIDA'].strip()}).",
        )

    try:
        qtd = Decimal(row['QUANTIDADE_DIARIAS'].strip().replace(',', '.'))
        if qtd <= 0:
            raise InvalidOperation
    except InvalidOperation:
        return None, f"Linha {line_num}: Quantidade de diárias inválida: {row['QUANTIDADE_DIARIAS']}."

    return {
        'credor': credor,
        'data_saida': data_saida,
        'data_retorno': data_retorno,
        'cidade_origem': row['CIDADE_ORIGEM'].strip(),
        'cidade_destino': row['CIDADE_DESTINO'].strip(),
        'objetivo': row['OBJETIVO'].strip(),
        'quantidade_diarias': qtd,
    }, None


_COLUNAS_REQUERIDAS = {
    'NOME_BENEFICIARIO', 'DATA_SAIDA', 'DATA_RETORNO',
    'CIDADE_ORIGEM', 'CIDADE_DESTINO', 'OBJETIVO', 'QUANTIDADE_DIARIAS',
}


def _gerar_anexar_scd_e_criar_assinatura(diaria, usuario_logado):
    """Gera SCD, anexa em DocumentoDiaria e cria rascunho de assinatura Autentique."""
    from processos.models import DocumentoDiaria, TiposDeDocumento
    from processos.models.fluxo import AssinaturaAutentique
    from processos.pdf_engine import gerar_documento_pdf
    from django.contrib.contenttypes.models import ContentType
    from django.core.files.base import ContentFile

    pdf_bytes = gerar_documento_pdf('scd', diaria)

    tipo_scd, _ = TiposDeDocumento.objects.get_or_create(
        tipo_de_documento__iexact='SOLICITAÇÃO DE CONCESSÃO DE DIÁRIAS (SCD)',
        defaults={'tipo_de_documento': 'SOLICITAÇÃO DE CONCESSÃO DE DIÁRIAS (SCD)'},
    )
    proxima_ordem = (diaria.documentos.aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1
    DocumentoDiaria.objects.create(
        diaria=diaria,
        arquivo=ContentFile(pdf_bytes, name=f"SCD_{diaria.id}.pdf"),
        tipo=tipo_scd,
        ordem=proxima_ordem,
    )

    assinatura = AssinaturaAutentique(
        content_type=ContentType.objects.get_for_model(diaria),
        object_id=diaria.id,
        tipo_documento='SCD',
        criador=usuario_logado,
        status='RASCUNHO',
    )
    assinatura.arquivo.save(
        f"SCD_{diaria.id}.pdf",
        ContentFile(pdf_bytes),
        save=True,
    )


def _open_diaria_csv(csv_file):
    """Decodifica e abre um CSV de diárias, retornando (reader, erro_str)."""
    try:
        conteudo = io.StringIO(csv_file.read().decode('utf-8'))
    except UnicodeDecodeError:
        return None, "Erro de codificação: verifique se o arquivo está salvo em UTF-8."

    reader = csv.DictReader(conteudo)

    if reader.fieldnames is None or not _COLUNAS_REQUERIDAS.issubset(set(reader.fieldnames)):
        faltando = _COLUNAS_REQUERIDAS - set(reader.fieldnames or [])
        return None, f"Cabeçalho inválido. Colunas ausentes: {', '.join(sorted(faltando))}."

    return reader, None


def preview_diarias_lote(csv_file):
    """Parse e valida um CSV de diárias sem inserir nada.

    Retorna um dict com:
        'preview'  – lista de dicts com os dados validados (seguros para JSON)
        'erros'    – lista de strings de erro
    """
    resultado = {'preview': [], 'erros': []}

    reader, erro = _open_diaria_csv(csv_file)
    if erro:
        resultado['erros'].append(erro)
        return resultado

    for row in reader:
        parsed, msg_erro = _parse_diaria_row(row, reader.line_num)
        if msg_erro:
            resultado['erros'].append(msg_erro)
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


def importar_diarias_lote(csv_file, usuario_logado):
    """Importa diárias diretamente de CSV, criando registros no banco.

    Retorna um dict com 'sucessos' (int) e 'erros' (lista de str).
    """
    from processos.models import Diaria

    resultados = {'sucessos': 0, 'erros': []}

    reader, erro = _open_diaria_csv(csv_file)
    if erro:
        resultados['erros'].append(erro)
        return resultados

    for row in reader:
        parsed, msg_erro = _parse_diaria_row(row, reader.line_num)
        if msg_erro:
            resultados['erros'].append(msg_erro)
            continue

        nova_diaria = Diaria.objects.create(
            beneficiario=parsed['credor'],
            proponente=usuario_logado,
            data_saida=parsed['data_saida'],
            data_retorno=parsed['data_retorno'],
            cidade_origem=parsed['cidade_origem'],
            cidade_destino=parsed['cidade_destino'],
            objetivo=parsed['objetivo'],
            quantidade_diarias=parsed['quantidade_diarias'],
            autorizada=False,
        )
        nova_diaria.avancar_status('SOLICITADA')
        try:
            _gerar_anexar_scd_e_criar_assinatura(nova_diaria, usuario_logado)
        except Exception as e:
            resultados['erros'].append(
                f"Diária {nova_diaria.numero_siscac or nova_diaria.id}: SCD não gerado ({e})"
            )
        resultados['sucessos'] += 1

    return resultados


def confirmar_diarias_lote(preview_items, usuario_logado):
    """Insere registros de Diária a partir de uma lista de dicts de preview validados.

    Cada dict em *preview_items* está no formato retornado por :func:`preview_diarias_lote`.
    Retorna um dict com 'sucessos' (int) e 'erros' (lista de str).
    """
    from processos.models import Diaria, Credor

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
            _gerar_anexar_scd_e_criar_assinatura(nova_diaria, usuario_logado)
        except Exception as e:
            resultados['erros'].append(
                f"Diária {nova_diaria.numero_siscac or nova_diaria.id}: SCD não gerado ({e})"
            )

        resultados['sucessos'] += 1

    return resultados

'''============================'''
'''SISCAC SYNC - DIÁRIAS'''
'''============================'''

def sync_diarias_siscac_csv(csv_file):
    """Importa/atualiza diárias a partir de CSV SISCAC padronizado por ponto e vírgula."""
    from processos.models import Diaria, Credor, StatusChoicesVerbasIndenizatorias

    resultados = {'criadas': 0, 'atualizadas': 0, 'erros': []}

    content = csv_file.read().decode('utf-8')
    reader = csv.reader(io.StringIO(content), delimiter=';')

    # Pula linhas de cabeçalho até encontrar o cabeçalho real da tabela
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
