"""Utilitários para importação de dados em CSV compartilhados entre domínios.

Este módulo implementa funções para decodificação, leitura e validação de arquivos CSV para importação em massa.
"""

import csv
import io
import logging


logger = logging.getLogger(__name__)

def decode_csv_file(csv_file, encodings, error_message):
    """Read and decode a binary CSV file with encoding fallback."""
    raw = csv_file.read()
    if isinstance(raw, str):
        return raw, None
    for encoding in encodings:
        try:
            return raw.decode(encoding), None
        except UnicodeDecodeError as exc:
            logger.warning("evento=erro_decode_csv encoding=%s erro=%s", encoding, exc)
            continue
    logger.error("evento=falha_decode_csv encodings_tentados=%s", ",".join(encodings))
    return None, error_message


def build_csv_dict_reader(
    csv_file,
    *,
    encodings,
    encoding_error_message,
    required_columns=None,
    missing_columns_message_prefix="Cabeçalho inválido. Colunas ausentes:",
):
    """Return a DictReader and optional error message for CSV import."""
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
