"""Utilitários de sincronização de diárias via CSV do SISCAC."""

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation


def sync_diarias_siscac_csv(csv_file):
    """Importa/atualiza diárias a partir de CSV SISCAC padronizado por ponto e vírgula."""
    from processos.models import Credor, Diaria, StatusChoicesVerbasIndenizatorias

    resultados = {'criadas': 0, 'atualizadas': 0, 'erros': []}

    content = csv_file.read().decode('utf-8')
    reader = csv.reader(io.StringIO(content), delimiter=';')

    # Pula linhas de cabeçalho até encontrar o cabeçalho real da tabela.
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
