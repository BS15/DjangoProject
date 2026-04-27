"""Servicos canonicos de sincronizacao SISCAC para diarias."""

from commons.shared.csv_import_utils import build_csv_dict_reader

from verbas_indenizatorias.models import Diaria

_COLUNAS_ID_DIARIA = ("DIARIA_ID", "ID_DIARIA", "ID", "PK")
_COLUNAS_NUMERO_SISCAC = (
    "NUMERO_SISCAC",
    "N_SISCAC",
    "NUMERO_DIARIA_SISCAC",
    "NUMERO_SISCAC_DIARIA",
)


def _primeiro_valor(row, candidates):
    for coluna in candidates:
        valor = (row.get(coluna) or "").strip()
        if valor:
            return valor
    return ""


def sincronizar_numero_siscac_csv(csv_file):
    """Concilia IDs de diarias com numero SISCAC a partir de CSV."""
    resultados = {"atualizadas": 0, "erros": []}
    reader, erro = build_csv_dict_reader(
        csv_file,
        encodings=("utf-8-sig", "utf-8", "latin-1"),
        encoding_error_message="Nao foi possivel decodificar o CSV. Use UTF-8 ou Latin-1.",
    )
    if erro:
        resultados["erros"].append(erro)
        return resultados

    for line_num, row in enumerate(reader, start=2):
        diaria_id_raw = _primeiro_valor(row, _COLUNAS_ID_DIARIA)
        numero_siscac = _primeiro_valor(row, _COLUNAS_NUMERO_SISCAC)

        if not diaria_id_raw:
            resultados["erros"].append(
                f"Linha {line_num}: informe o identificador da diaria ({', '.join(_COLUNAS_ID_DIARIA)})."
            )
            continue

        if not numero_siscac:
            resultados["erros"].append(
                f"Linha {line_num}: informe o numero SISCAC ({', '.join(_COLUNAS_NUMERO_SISCAC)})."
            )
            continue

        try:
            diaria_id = int(diaria_id_raw)
            diaria = Diaria.objects.get(pk=diaria_id)
            if (diaria.numero_siscac or "") == numero_siscac:
                continue

            diaria.numero_siscac = numero_siscac
            diaria.save(update_fields=["numero_siscac"])
            resultados["atualizadas"] += 1
        except ValueError:
            resultados["erros"].append(f"Linha {line_num}: ID de diaria invalido ('{diaria_id_raw}').")
        except Diaria.DoesNotExist:
            resultados["erros"].append(f"Linha {line_num}: diaria ID {diaria_id_raw} nao encontrada.")
        except Exception as exc:  # pragma: no cover - seguranca para erro inesperado por linha
            resultados["erros"].append(
                f"Linha {line_num}: erro ao sincronizar diaria ID {diaria_id_raw}: {exc}"
            )

    return resultados


__all__ = ["sincronizar_numero_siscac_csv"]
