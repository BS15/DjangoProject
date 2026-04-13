"""Serviços de importação e sincronização de diárias no próprio domínio de verbas."""


from commons.shared.csv_import_utils import decode_csv_file, build_csv_dict_reader
from datetime import datetime
from decimal import Decimal, InvalidOperation

from credores.models import Credor
from verbas_indenizatorias.models import Diaria, StatusChoicesVerbasIndenizatorias
from verbas_indenizatorias.services.documentos import gerar_e_anexar_scd_diaria


class DiariaCsvValidationError(Exception):
    """Erro de validação de linha de diária em importação CSV."""


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
        raise DiariaCsvValidationError(f"Linha {line_num}: Quantidade de diárias inválida.")

    return {
        "beneficiario_id": credor.id,
        "beneficiario_nome": credor.nome,
        "data_saida": data_saida.isoformat(),
        "data_retorno": data_retorno.isoformat(),
        "quantidade_diarias": str(qtd),
        "cidade_origem": row.get("CIDADE_ORIGEM", "").strip(),
        "cidade_destino": row.get("CIDADE_DESTINO", "").strip(),
        "objetivo": row.get("OBJETIVO", "").strip(),
        "tipo_solicitacao": row.get("TIPO_SOLICITACAO", "INICIAL").strip() or "INICIAL",
    }


def preview_diarias_lote(csv_file):
    """Lê o arquivo CSV e retorna preview (lista de dicts serializáveis) e erros."""
    preview = []
    erros = []
    try:
        csv_bytes = decode_csv_file(csv_file)
        reader = build_csv_dict_reader(csv_bytes)
        for line_num, row in enumerate(reader, start=2):
            try:
                preview.append(_parse_diaria_row(row, line_num))
            except DiariaCsvValidationError as exc:
                erros.append(str(exc))
    except Exception as exc:
        erros.append(f"Erro ao ler arquivo: {exc}")
    return {"preview": preview, "erros": erros}


def confirmar_diarias_lote(preview_items, usuario):
    """Cria objetos Diaria a partir dos dicts da prévia e gera SCDs."""
    from datetime import date

    resultados = []
    status_obj, _ = StatusChoicesVerbasIndenizatorias.objects.get_or_create(
        status_choice__iexact="AGUARDANDO AUTORIZAÇÃO",
        defaults={"status_choice": "AGUARDANDO AUTORIZAÇÃO"},
    )
    for item in preview_items:
        try:
            diaria = Diaria.objects.create(
                beneficiario_id=item["beneficiario_id"],
                proponente=usuario,
                data_saida=date.fromisoformat(item["data_saida"]),
                data_retorno=date.fromisoformat(item["data_retorno"]),
                quantidade_diarias=Decimal(item["quantidade_diarias"]),
                cidade_origem=item.get("cidade_origem", ""),
                cidade_destino=item.get("cidade_destino", ""),
                objetivo=item.get("objetivo", ""),
                tipo_solicitacao=item.get("tipo_solicitacao", "INICIAL"),
                status=status_obj,
            )
            gerar_e_anexar_scd_diaria(diaria, usuario)
            resultados.append({"ok": True, "diaria_id": diaria.id, "nome": item["beneficiario_nome"]})
        except Exception as exc:
            resultados.append({"ok": False, "nome": item.get("beneficiario_nome", "?"), "erro": str(exc)})
    return resultados
