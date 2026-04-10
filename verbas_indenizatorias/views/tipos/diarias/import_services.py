"""Serviços de importação e sincronização de diárias no próprio domínio de verbas."""

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from credores.models import Credor
from verbas_indenizatorias.models import Diaria, StatusChoicesVerbasIndenizatorias
from verbas_indenizatorias.services.diarias import gerar_e_anexar_scd_diaria


class DiariaCsvValidationError(Exception):
    """Erro de validação de linha de diária em importação CSV."""


def decode_csv_file(csv_file, encodings, error_message):
    raw = csv_file.read()
    if isinstance(raw, str):
        return raw, None
    for encoding in encodings:
        try:
            return raw.decode(encoding), None
        except UnicodeDecodeError:
            continue
    return None, error_message


def build_csv_dict_reader(
    csv_file,
    *,
    encodings,
    encoding_error_message,
    required_columns=None,
    missing_columns_message_prefix="Cabeçalho inválido. Colunas ausentes:",
):
    decoded, error = decode_csv_file(csv_file, encodings, encoding_error_message)
    if error:
        return None, error
    reader = csv.DictReader(io.StringIO(decoded))
    if required_columns is None:
        return reader, None
    fieldnames = set(reader.fieldnames or [])
    if not set(required_columns).issubset(fieldnames):
        faltando = set(required_columns) - fieldnames
        return None, f"{missing_columns_message_prefix} {', '.join(sorted(faltando))}."
    return reader, None


def _parse_diaria_row(row, line_num):
    nome = row.get("NOME_BENEFICIARIO", "").strip()
    credor = Credor.objects.filter(nome__iexact=nome, tipo="PF").first() or Credor.objects.filter(
        nome__icontains=nome, tipo="PF"
    ).first()
    if not credor:
        raise DiariaCsvValidationError(f"Linha {line_num}: Beneficiário '{nome}' não encontrado no sistema.")

    try:
        data_saida = datetime.strptime(row["DATA_SAIDA"].strip(), "%d/%m/%Y").date()
        data_retorno = datetime.strptime(row["DATA_RETORNO"].strip(), "%d/%m/%Y").date()
    except ValueError:
        raise DiariaCsvValidationError(f"Linha {line_num}: Data inválida. Use o formato DD/MM/AAAA.")

    if data_retorno < data_saida:
        raise DiariaCsvValidationError(
            f"Linha {line_num}: Data de retorno ({row['DATA_RETORNO'].strip()}) não pode ser anterior à data de saída ({row['DATA_SAIDA'].strip()})."
        )

    try:
        qtd = Decimal(row["QUANTIDADE_DIARIAS"].strip().replace(",", "."))
        if qtd <= 0:
            raise InvalidOperation
    except InvalidOperation:
        raise DiariaCsvValidationError(
            f"Linha {line_num}: Quantidade de diárias inválida: {row['QUANTIDADE_DIARIAS']}."
        )

    return {
        "credor": credor,
        "data_saida": data_saida,
        "data_retorno": data_retorno,
        "cidade_origem": row["CIDADE_ORIGEM"].strip(),
        "cidade_destino": row["CIDADE_DESTINO"].strip(),
        "objetivo": row["OBJETIVO"].strip(),
        "quantidade_diarias": qtd,
    }


def _open_diaria_csv(csv_file):
    colunas = {
        "NOME_BENEFICIARIO",
        "DATA_SAIDA",
        "DATA_RETORNO",
        "CIDADE_ORIGEM",
        "CIDADE_DESTINO",
        "OBJETIVO",
        "QUANTIDADE_DIARIAS",
    }
    return build_csv_dict_reader(
        csv_file,
        encodings=("utf-8",),
        encoding_error_message="Erro de codificação: verifique se o arquivo está salvo em UTF-8.",
        required_columns=colunas,
        missing_columns_message_prefix="Cabeçalho inválido. Colunas ausentes:",
    )


def preview_diarias_lote(csv_file):
    resultado = {"preview": [], "erros": []}
    reader, erro = _open_diaria_csv(csv_file)
    if erro:
        resultado["erros"].append(erro)
        return resultado

    for row in reader:
        try:
            parsed = _parse_diaria_row(row, reader.line_num)
        except DiariaCsvValidationError as exc:
            resultado["erros"].append(str(exc))
            continue

        credor = parsed["credor"]
        resultado["preview"].append(
            {
                "beneficiario_id": credor.pk,
                "beneficiario_nome": credor.nome,
                "data_saida": parsed["data_saida"].strftime("%Y-%m-%d"),
                "data_retorno": parsed["data_retorno"].strftime("%Y-%m-%d"),
                "data_saida_display": parsed["data_saida"].strftime("%d/%m/%Y"),
                "data_retorno_display": parsed["data_retorno"].strftime("%d/%m/%Y"),
                "cidade_origem": parsed["cidade_origem"],
                "cidade_destino": parsed["cidade_destino"],
                "objetivo": parsed["objetivo"],
                "quantidade_diarias": str(parsed["quantidade_diarias"]),
            }
        )
    return resultado


def confirmar_diarias_lote(preview_items, usuario_logado):
    resultados = {"sucessos": 0, "erros": []}
    for item in preview_items:
        credor = Credor.objects.filter(pk=item["beneficiario_id"], tipo="PF").first()
        if credor is None:
            resultados["erros"].append(
                f"Beneficiário com ID {item['beneficiario_id']} não encontrado ao confirmar."
            )
            continue

        nova_diaria = Diaria.objects.create(
            beneficiario=credor,
            proponente=usuario_logado,
            data_saida=datetime.strptime(item["data_saida"], "%Y-%m-%d").date(),
            data_retorno=datetime.strptime(item["data_retorno"], "%Y-%m-%d").date(),
            cidade_origem=item["cidade_origem"],
            cidade_destino=item["cidade_destino"],
            objetivo=item["objetivo"],
            quantidade_diarias=Decimal(item["quantidade_diarias"]),
            autorizada=False,
        )
        nova_diaria.avancar_status("SOLICITADA")
        try:
            gerar_e_anexar_scd_diaria(nova_diaria, usuario_logado)
        except (OSError, RuntimeError, TypeError, ValueError) as e:
            resultados["erros"].append(
                f"Diária {nova_diaria.numero_siscac or nova_diaria.id}: SCD não gerado ({e})"
            )
        resultados["sucessos"] += 1
    return resultados


def sync_diarias_siscac_csv(csv_file):
    resultados = {"criadas": 0, "atualizadas": 0, "erros": []}
    content = csv_file.read().decode("utf-8")
    reader = csv.reader(io.StringIO(content), delimiter=";")

    for line in reader:
        if line and line[0].strip() == "Número":
            break

    for row in reader:
        if not row or not row[0].strip():
            continue
        try:
            numero_csv = row[0].strip()
            row_name = row[1].strip() if len(row) > 1 else ""
            destino = row[3].strip() if len(row) > 3 else ""
            saida_str = row[4].strip() if len(row) > 4 else ""
            retorno_str = row[6].strip() if len(row) > 6 else ""
            situacao_str = row[7].strip() if len(row) > 7 else ""
            motivo = row[8].strip() if len(row) > 8 else ""
            qtd_str = row[10].strip() if len(row) > 10 else ""
            valor_str = row[13].strip() if len(row) > 13 else ""
        except IndexError:
            resultados["erros"].append(f"Linha malformada: {row}")
            continue

        if not row_name:
            continue

        try:
            saida = datetime.strptime(saida_str, "%d/%m/%Y").date() if saida_str else None
            retorno = datetime.strptime(retorno_str, "%d/%m/%Y").date() if retorno_str else None
        except ValueError:
            resultados["erros"].append(f"Data inválida na linha com Nº {numero_csv}")
            continue

        try:
            valor_diaria = Decimal(valor_str.replace(".", "").replace(",", ".")) if valor_str else None
        except InvalidOperation:
            valor_diaria = None

        try:
            quantidade = Decimal(qtd_str.replace(",", ".")) if qtd_str else Decimal("1")
        except InvalidOperation:
            quantidade = Decimal("1")

        credor = Credor.objects.filter(nome__icontains=row_name).first()
        if credor is None:
            resultados["erros"].append(f"Credor não encontrado para: {row_name}")
            continue

        status_obj = None
        if situacao_str:
            status_obj = StatusChoicesVerbasIndenizatorias.objects.filter(status_choice__iexact=situacao_str).first()
            if status_obj is None:
                status_obj = StatusChoicesVerbasIndenizatorias.objects.create(status_choice=situacao_str)

        _, created = Diaria.objects.update_or_create(
            numero_siscac=numero_csv,
            defaults={
                "beneficiario": credor,
                "data_saida": saida,
                "data_retorno": retorno,
                "cidade_destino": destino or "-",
                "cidade_origem": "-",
                "objetivo": motivo or "-",
                "quantidade_diarias": quantidade,
                "valor_total": valor_diaria,
                "status": status_obj,
            },
        )
        if created:
            resultados["criadas"] += 1
        else:
            resultados["atualizadas"] += 1

    return resultados
