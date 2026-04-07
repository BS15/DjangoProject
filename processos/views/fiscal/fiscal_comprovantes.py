"""Views de comprovantes pos-pagamento."""

import json

from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from ...models import ComprovanteDePagamento, DocumentoDePagamento, Processo, TiposDeDocumento
from ...utils import split_pdf_to_temp_pages, processar_pdf_comprovantes


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def painel_comprovantes_view(request):
    processos_lancados = Processo.objects.filter(
        status__status_choice__iexact="LANÇADO - AGUARDANDO COMPROVANTE"
    ).select_related("credor").order_by("credor__nome", "id")

    processos_list = []
    for processo in processos_lancados:
        processos_list.append(
            {
                "id": processo.id,
                "credor_nome": processo.credor.nome if processo.credor else "Sem Credor",
                "valor_liquido": str(processo.valor_liquido or "0.00"),
                "n_nota_empenho": processo.n_nota_empenho or "S/N",
            }
        )

    context = {"processos_json": json.dumps(processos_list)}
    return render(request, "fiscal/painel_comprovantes.html", context)


def serializar_comprovante(comp):
    """Converte o resultado de um comprovante para estrutura serializável em JSON."""
    return {
        **comp,
        "documentos_encontrados": [
            {"doc": item["doc"], "credor": getattr(item["credor"], "nome", None)}
            for item in comp.get("documentos_encontrados", [])
        ],
        "contas_encontradas": [
            {
                "agencia": item["agencia"],
                "conta": item["conta"],
                "credor": getattr(item["credor"], "nome", None),
            }
            for item in comp.get("contas_encontradas", [])
        ],
    }


_serializar_comprovante = serializar_comprovante


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def api_fatiar_comprovantes(request):
    if request.method == "POST" and request.FILES.get("pdf_banco"):
        modo = request.POST.get("modo", "auto")

        try:
            if modo == "manual":
                resultados = split_pdf_to_temp_pages(request.FILES["pdf_banco"])
            else:
                resultados = processar_pdf_comprovantes(request.FILES["pdf_banco"])

            resultados_json = [serializar_comprovante(resultado) for resultado in resultados]
            return JsonResponse({"sucesso": True, "comprovantes": resultados_json, "modo": modo})
        except Exception as exc:
            return JsonResponse({"sucesso": False, "erro": str(exc)})
    return JsonResponse({"sucesso": False, "erro": "Arquivo não enviado."})


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def api_vincular_comprovantes(request):
    if request.method == "POST":
        try:
            dados = json.loads(request.body)
            processo_id = dados.get("processo_id")
            comprovantes = dados.get("comprovantes", [])

            if not processo_id:
                return JsonResponse({"sucesso": False, "erro": "ID do processo não informado."})

            if not comprovantes:
                return JsonResponse({"sucesso": False, "erro": "Nenhum comprovante enviado."})

            processo = get_object_or_404(Processo, id=processo_id)

            if not processo.status or processo.status.status_choice.upper() != "LANÇADO - AGUARDANDO COMPROVANTE":
                return JsonResponse(
                    {
                        "sucesso": False,
                        "erro": f"Processo #{processo_id} não está no status correto. Status atual: {processo.status}",
                    }
                )

            tipo_comprovante, _ = TiposDeDocumento.objects.get_or_create(
                tipo_de_documento__iexact="Comprovante de Pagamento",
                defaults={"tipo_de_documento": "Comprovante de Pagamento"},
            )

            temp_paths_to_delete = []
            data_pagamento_processo = None

            try:
                with transaction.atomic():
                    for idx, comprovante in enumerate(comprovantes):
                        temp_path = comprovante.get("temp_path")
                        if not temp_path:
                            continue

                        valor_pago = comprovante.get("valor_pago")
                        credor_nome = comprovante.get("credor_nome") or ""
                        data_pagamento = comprovante.get("data_pagamento") or None
                        numero_comprovante = comprovante.get("numero_comprovante") or None

                        if data_pagamento and not data_pagamento_processo:
                            data_pagamento_processo = data_pagamento

                        if default_storage.exists(temp_path):
                            with default_storage.open(temp_path) as temp_file:
                                conteudo_arquivo = temp_file.read()

                            nome_arquivo = f"Comprovante_Proc_{processo.id}_{idx + 1}.pdf"

                            DocumentoDePagamento.objects.create(
                                processo=processo,
                                arquivo=ContentFile(conteudo_arquivo, name=nome_arquivo),
                                tipo=tipo_comprovante,
                                ordem=99,
                            )

                            ComprovanteDePagamento.objects.create(
                                processo=processo,
                                credor_nome=credor_nome,
                                valor_pago=valor_pago,
                                data_pagamento=data_pagamento,
                                numero_comprovante=numero_comprovante,
                                arquivo=ContentFile(conteudo_arquivo, name=nome_arquivo),
                            )

                            temp_paths_to_delete.append(temp_path)

                    processo.avancar_status("PAGO - EM CONFERÊNCIA", usuario=request.user)

                    if data_pagamento_processo:
                        processo.data_pagamento = data_pagamento_processo
                        processo.save(update_fields=["data_pagamento"])

                        for nota in processo.notas_fiscais.all():
                            for retencao in nota.retencoes.filter(codigo__regra_competencia="pagamento"):
                                retencao.save(update_fields=["competencia"])
            except ValidationError as exc:
                return JsonResponse({"sucesso": False, "erro": " ".join(exc.messages)})

            for temp_path in temp_paths_to_delete:
                try:
                    default_storage.delete(temp_path)
                except Exception:
                    pass

            return JsonResponse(
                {
                    "sucesso": True,
                    "mensagem": f'Processo #{processo_id} baixado com sucesso! Status alterado para "PAGO - EM CONFERÊNCIA".',
                }
            )
        except Exception as exc:
            return JsonResponse({"sucesso": False, "erro": str(exc)})

    return JsonResponse({"sucesso": False, "erro": "Método inválido."})
