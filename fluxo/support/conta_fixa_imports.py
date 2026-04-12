from django.http import HttpResponse
from django.contrib.auth.decorators import permission_required
@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def download_template_csv_contas(request):
    """Disponibiliza template CSV para importação de contas fixas."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="template_contas_fixas.csv"'
    writer = csv.writer(response)
    writer.writerow(["NOME_CREDOR", "DIA_VENCIMENTO", "DETALHAMENTO"])
    return response
import csv
from django.db import DatabaseError
from credores.models import Credor
from .conta_fixa_models import ContaFixa

def importar_contas_fixas_csv(csv_file):
    """Importa contas fixas via CSV."""
    resultados = {"sucessos": 0, "erros": []}
    reader, erro = build_csv_dict_reader(
        csv_file,
        encodings=("utf-8-sig", "latin-1"),
        encoding_error_message="Erro de codificação: não foi possível ler o CSV.",
    )
    if erro:
        resultados["erros"].append(erro)
        return resultados

    for row in reader:
        try:
            nome_credor = row["NOME_CREDOR"].strip()
            credor = Credor.objects.filter(nome__iexact=nome_credor).first()
            if not credor:
                resultados["erros"].append(f"Linha {reader.line_num}: Credor '{nome_credor}' não encontrado.")
                continue

            ContaFixa.objects.get_or_create(
                credor=credor,
                referencia=row["DETALHAMENTO"].strip(),
                defaults={"dia_vencimento": int(row["DIA_VENCIMENTO"]), "ativa": True},
            )
            resultados["sucessos"] += 1
        except ValueError as e:
            resultados["erros"].append(f"Linha {reader.line_num}: {e}")
        except (KeyError, AttributeError, TypeError, DatabaseError) as e:
            resultados["erros"].append(f"Linha {reader.line_num}: {e}")
    return resultados
