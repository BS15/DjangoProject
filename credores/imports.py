import csv
import io

from django.contrib.auth.decorators import permission_required
from django.db import DatabaseError
from django.http import HttpResponse
from django.shortcuts import render

from credores.models import CargosFuncoes, ContaFixa, ContasBancarias, Credor


def decode_csv_file(csv_file, encodings, error_message):
    """Lê e decodifica CSV binário com fallback de encodings."""
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
    """Retorna DictReader e mensagem de erro opcional para importação."""
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


def importar_credores_csv(csv_file):
    """Importa credores via CSV."""
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
            cpf_cnpj_limpo = (
                row["CPF_CNPJ"].replace(".", "").replace("-", "").replace("/", "").replace(" ", "").strip()
            )
            tipo = "PF" if len(cpf_cnpj_limpo) == 11 else "PJ"
            defaults = {"nome": row["NOME"].strip(), "tipo": tipo}

            grupo_nome = row.get("GRUPO", "").strip()
            cargo_nome = row.get("CARGO_FUNCAO", "").strip()
            if grupo_nome and cargo_nome:
                cargo_obj, _ = CargosFuncoes.objects.get_or_create(grupo=grupo_nome, cargo_funcao=cargo_nome)
                defaults["cargo_funcao"] = cargo_obj

            credor, _ = Credor.objects.get_or_create(cpf_cnpj=cpf_cnpj_limpo, defaults=defaults)
            banco = row.get("BANCO", "").strip() or None
            agencia = row.get("AGENCIA", "").strip() or None
            conta_num = row.get("CONTA", "").strip() or None
            pix = row.get("PIX", "").strip() or None

            if banco or agencia or conta_num:
                conta_bancaria, _ = ContasBancarias.objects.get_or_create(
                    titular=credor,
                    banco=banco,
                    agencia=agencia,
                    conta=conta_num,
                )
                if credor.conta_id != conta_bancaria.pk:
                    credor.conta = conta_bancaria
                    credor.save(update_fields=["conta"])

            if pix and credor.chave_pix != pix:
                credor.chave_pix = pix
                credor.save(update_fields=["chave_pix"])

            resultados["sucessos"] += 1
        except (KeyError, AttributeError, ValueError, TypeError, DatabaseError) as e:
            resultados["erros"].append(f"Linha {reader.line_num}: {e}")
    return resultados


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


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def painel_importacao_view(request):
    """Renderiza painel de importação em lote de credores e contas fixas."""
    context = {}
    if request.method == "POST":
        if "importar_credores" in request.POST:
            if "file_credores" not in request.FILES:
                context["resultados"] = {"sucessos": 0, "erros": ["Nenhum arquivo foi enviado."]}
            else:
                resultados = importar_credores_csv(request.FILES["file_credores"])
                context["resultados"] = resultados
            context["tipo_importacao"] = "Credores"
        elif "importar_contas" in request.POST:
            if "file_contas" not in request.FILES:
                context["resultados"] = {"sucessos": 0, "erros": ["Nenhum arquivo foi enviado."]}
            else:
                resultados = importar_contas_fixas_csv(request.FILES["file_contas"])
                context["resultados"] = resultados
            context["tipo_importacao"] = "Contas Fixas"
    return render(request, "fluxo/painel_importacao.html", context)


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def download_template_csv_credores(request):
    """Disponibiliza template CSV para importação de credores."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="template_credores.csv"'
    writer = csv.writer(response)
    writer.writerow(["NOME", "CPF_CNPJ", "GRUPO", "CARGO_FUNCAO", "BANCO", "AGENCIA", "CONTA", "PIX"])
    return response


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def download_template_csv_contas(request):
    """Disponibiliza template CSV para importação de contas fixas."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="template_contas_fixas.csv"'
    writer = csv.writer(response)
    writer.writerow(["NOME_CREDOR", "DIA_VENCIMENTO", "DETALHAMENTO"])
    return response
