"""Importação em lote de diárias via CSV."""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from ...csv_common import build_csv_dict_reader
from .errors import DiariaCsvValidationError


_COLUNAS_REQUERIDAS = {
    'NOME_BENEFICIARIO',
    'DATA_SAIDA',
    'DATA_RETORNO',
    'CIDADE_ORIGEM',
    'CIDADE_DESTINO',
    'OBJETIVO',
    'QUANTIDADE_DIARIAS',
}


def _parse_diaria_row(row, line_num):
    """Valida e converte uma linha de CSV de diária."""
    from processos.models.segments.cadastros import Credor

    nome = row.get('NOME_BENEFICIARIO', '').strip()
    credor = (
        Credor.objects.filter(nome__iexact=nome, tipo='PF').first()
        or Credor.objects.filter(nome__icontains=nome, tipo='PF').first()
    )

    if not credor:
        raise DiariaCsvValidationError(
            f"Linha {line_num}: Beneficiário '{nome}' não encontrado no sistema."
        )

    try:
        data_saida = datetime.strptime(row['DATA_SAIDA'].strip(), '%d/%m/%Y').date()
        data_retorno = datetime.strptime(row['DATA_RETORNO'].strip(), '%d/%m/%Y').date()
    except ValueError:
        raise DiariaCsvValidationError(
            f"Linha {line_num}: Data inválida. Use o formato DD/MM/AAAA."
        )

    if data_retorno < data_saida:
        raise DiariaCsvValidationError(
            f"Linha {line_num}: Data de retorno ({row['DATA_RETORNO'].strip()}) "
            f"não pode ser anterior à data de saída ({row['DATA_SAIDA'].strip()}).",
        )

    try:
        qtd = Decimal(row['QUANTIDADE_DIARIAS'].strip().replace(',', '.'))
        if qtd <= 0:
            raise InvalidOperation
    except InvalidOperation:
        raise DiariaCsvValidationError(
            f"Linha {line_num}: Quantidade de diárias inválida: {row['QUANTIDADE_DIARIAS']}."
        )

    return {
        'credor': credor,
        'data_saida': data_saida,
        'data_retorno': data_retorno,
        'cidade_origem': row['CIDADE_ORIGEM'].strip(),
        'cidade_destino': row['CIDADE_DESTINO'].strip(),
        'objetivo': row['OBJETIVO'].strip(),
        'quantidade_diarias': qtd,
    }


def _open_diaria_csv(csv_file):
    """Abre CSV de diárias em UTF-8 e valida o cabeçalho obrigatório."""
    return build_csv_dict_reader(
        csv_file,
        encodings=('utf-8',),
        encoding_error_message='Erro de codificação: verifique se o arquivo está salvo em UTF-8.',
        required_columns=_COLUNAS_REQUERIDAS,
        missing_columns_message_prefix='Cabeçalho inválido. Colunas ausentes:',
    )


def _gerar_anexar_scd_e_criar_assinatura(diaria, usuario_logado):
    """Gera SCD da diária, anexa o PDF e cria rascunho de assinatura digital."""
    from processos.services.verbas.diarias import gerar_e_anexar_scd_diaria

    gerar_e_anexar_scd_diaria(diaria, usuario_logado)


def preview_diarias_lote(csv_file):
    """Lê e valida um CSV de diárias sem inserir registros no banco."""
    resultado = {'preview': [], 'erros': []}

    reader, erro = _open_diaria_csv(csv_file)
    if erro:
        resultado['erros'].append(erro)
        return resultado

    for row in reader:
        try:
            parsed = _parse_diaria_row(row, reader.line_num)
        except DiariaCsvValidationError as exc:
            resultado['erros'].append(str(exc))
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
    """Importa diárias de CSV, cria registros e tenta anexar SCD automático."""
    from processos.models.segments.core import Diaria

    resultados = {'sucessos': 0, 'erros': []}

    reader, erro = _open_diaria_csv(csv_file)
    if erro:
        resultados['erros'].append(erro)
        return resultados

    for row in reader:
        try:
            parsed = _parse_diaria_row(row, reader.line_num)
        except DiariaCsvValidationError as exc:
            resultados['erros'].append(str(exc))
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
        except (OSError, RuntimeError, TypeError, ValueError) as e:
            resultados['erros'].append(
                f"Diária {nova_diaria.numero_siscac or nova_diaria.id}: SCD não gerado ({e})"
            )
        resultados['sucessos'] += 1

    return resultados


def confirmar_diarias_lote(preview_items, usuario_logado):
    """Confirma o preview e insere diárias validadas no banco."""
    from processos.models.segments.cadastros import Credor
    from processos.models.segments.core import Diaria

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
        except (OSError, RuntimeError, TypeError, ValueError) as e:
            resultados['erros'].append(
                f"Diária {nova_diaria.numero_siscac or nova_diaria.id}: SCD não gerado ({e})"
            )

        resultados['sucessos'] += 1

    return resultados


__all__ = [
    '_open_diaria_csv',
    '_parse_diaria_row',
    'confirmar_diarias_lote',
    'importar_diarias_lote',
    'preview_diarias_lote',
]