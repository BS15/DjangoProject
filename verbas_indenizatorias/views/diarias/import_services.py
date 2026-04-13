"""Serviços de importação e sincronização de diárias no próprio domínio de verbas."""


from commons.shared.csv_import_utils import decode_csv_file, build_csv_dict_reader
from datetime import datetime
from decimal import Decimal, InvalidOperation

from credores.models import Credor
from verbas_indenizatorias.models import Diaria, StatusChoicesVerbasIndenizatorias
from verbas_indenizatorias.services.diarias import gerar_e_anexar_scd_diaria


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
    # ...rest of the function...
