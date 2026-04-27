"""Servicos canonicos de importacao em lote para diarias."""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from commons.shared.csv_import_utils import build_csv_dict_reader

from credores.models import Credor
from verbas_indenizatorias.constants import STATUS_VERBA_APROVADA, STATUS_VERBA_SOLICITADA
from verbas_indenizatorias.models import Diaria
from verbas_indenizatorias.services.documentos import gerar_e_anexar_pcd_diaria


class DiariaCsvValidationError(Exception):
    """Erro de validacao de linha de diaria em importacao CSV."""


def _parse_diaria_row(row, line_num):
    nome = row.get("NOME_BENEFICIARIO", "").strip()
    credor = Credor.objects.filter(nome__iexact=nome, tipo="PF").first() or Credor.objects.filter(
        nome__icontains=nome, tipo="PF"
    ).first()
    if not credor:
        raise DiariaCsvValidationError(f"Linha {line_num}: Beneficiario '{nome}' nao encontrado no sistema.")

    try:
        data_saida = datetime.strptime(row["DATA_SAIDA"].strip(), "%d/%m/%Y").date()
        data_retorno = datetime.strptime(row["DATA_RETORNO"].strip(), "%d/%m/%Y").date()
    except ValueError as exc:
        raise DiariaCsvValidationError(f"Linha {line_num}: Data invalida. Use o formato DD/MM/AAAA.") from exc

    raw_solicitacao = row.get("DATA_SOLICITACAO", "").strip()
    if raw_solicitacao:
        try:
            data_solicitacao = datetime.strptime(raw_solicitacao, "%d/%m/%Y").date()
        except ValueError as exc:
            raise DiariaCsvValidationError(
                f"Linha {line_num}: DATA_SOLICITACAO invalida. Use o formato DD/MM/AAAA."
            ) from exc
    else:
        data_solicitacao = datetime.today().date()

    if data_retorno < data_saida:
        raise DiariaCsvValidationError(
            f"Linha {line_num}: Data de retorno ({row['DATA_RETORNO'].strip()}) nao pode ser anterior a data de saida ({row['DATA_SAIDA'].strip()})."
        )

    try:
        qtd = Decimal(row["QUANTIDADE_DIARIAS"].strip().replace(",", "."))
        if qtd <= 0:
            raise InvalidOperation
    except InvalidOperation as exc:
        raise DiariaCsvValidationError(f"Linha {line_num}: Quantidade de diarias invalida.") from exc

    return {
        "beneficiario_id": credor.id,
        "beneficiario_nome": credor.nome,
        "data_solicitacao": data_solicitacao.isoformat(),
        "data_saida": data_saida.isoformat(),
        "data_retorno": data_retorno.isoformat(),
        "quantidade_diarias": str(qtd),
        "cidade_origem": row.get("CIDADE_ORIGEM", "").strip(),
        "cidade_destino": row.get("CIDADE_DESTINO", "").strip(),
        "objetivo": row.get("OBJETIVO", "").strip(),
        "tipo_solicitacao": row.get("TIPO_SOLICITACAO", "INICIAL").strip() or "INICIAL",
    }


def preview_diarias_lote(csv_file):
    """Le o arquivo CSV e retorna preview serializavel com erros."""
    preview = []
    erros = []
    try:
        reader, erro = build_csv_dict_reader(
            csv_file,
            encodings=("utf-8-sig", "utf-8", "latin-1"),
            encoding_error_message="Nao foi possivel decodificar o CSV. Use UTF-8 ou Latin-1.",
        )
        if erro:
            return {"preview": [], "erros": [erro]}

        for line_num, row in enumerate(reader, start=2):
            try:
                preview.append(_parse_diaria_row(row, line_num))
            except DiariaCsvValidationError as exc:
                erros.append(str(exc))
    except Exception as exc:
        erros.append(f"Erro ao ler arquivo: {exc}")
    return {"preview": preview, "erros": erros}


def confirmar_diarias_lote(preview_items, usuario):
    """Compat: cria diarias em lote no modo padrao (solicitacao para autorizacao)."""
    return confirmar_diarias_lote_com_modo(preview_items, usuario, solicitacao_assinada=False)


def confirmar_diarias_lote_com_modo(preview_items, usuario, solicitacao_assinada=False):
    """Cria diarias em lote no modo padrao ou no modo de solicitacao ja assinada."""
    from datetime import date

    resultados = {"sucessos": 0, "erros": [], "modo_solicitacao_assinada": bool(solicitacao_assinada)}
    status_destino = STATUS_VERBA_APROVADA if solicitacao_assinada else STATUS_VERBA_SOLICITADA

    for item in preview_items:
        try:
            diaria = Diaria.objects.create(
                beneficiario_id=item["beneficiario_id"],
                proponente=usuario,
                data_solicitacao=date.fromisoformat(item["data_solicitacao"]),
                data_saida=date.fromisoformat(item["data_saida"]),
                data_retorno=date.fromisoformat(item["data_retorno"]),
                quantidade_diarias=Decimal(item["quantidade_diarias"]),
                cidade_origem=item.get("cidade_origem", ""),
                cidade_destino=item.get("cidade_destino", ""),
                objetivo=item.get("objetivo", ""),
                tipo_solicitacao=item.get("tipo_solicitacao", "INICIAL"),
            )
            diaria.definir_status(status_destino, autorizada=bool(solicitacao_assinada))
            if solicitacao_assinada:
                gerar_e_anexar_pcd_diaria(diaria, criador=usuario)
            resultados["sucessos"] += 1
        except Exception as exc:
            resultados["erros"].append(f"{item.get('beneficiario_nome', '?')}: {exc}")

    return resultados


__all__ = [
    "DiariaCsvValidationError",
    "preview_diarias_lote",
    "confirmar_diarias_lote",
    "confirmar_diarias_lote_com_modo",
]
