

"""Funções de importação em lote para credores e contas fixas.

Este módulo implementa utilitários para importação de dados via CSV, painel de importação e download de templates.
"""

from commons.shared.csv_import_utils import decode_csv_file, build_csv_dict_reader

from django.contrib.auth.decorators import permission_required

from django.db import DatabaseError
from django.http import HttpResponse
from django.shortcuts import render

from credores.models import CargosFuncoes, ContasBancarias, Credor



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





@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
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
    return render(request, "pagamentos/painel_importacao.html", context)


@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def download_template_csv_credores(request):
    """Disponibiliza template CSV para importação de credores."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="template_credores.csv"'
    writer = csv.writer(response)
    writer.writerow(["NOME", "CPF_CNPJ", "GRUPO", "CARGO_FUNCAO", "BANCO", "AGENCIA", "CONTA", "PIX"])
    return response


