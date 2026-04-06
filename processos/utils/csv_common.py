"""Helpers compartilhados para abertura e validação de CSV."""

import csv
import io


def decode_csv_file(csv_file, encodings, error_message):
    """Lê um arquivo CSV binário e tenta decodificar usando uma lista de encodings."""
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
    missing_columns_message_prefix='Cabeçalho inválido. Colunas ausentes:',
):
    """Retorna ``(DictReader, None)`` ou ``(None, mensagem_erro)``."""
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
