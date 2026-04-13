"""Endpoints POST/API da etapa de comprovantes de pagamento."""

import json
import logging

import PyPDF2
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from fluxo.domain_models.comprovantes import ComprovanteDePagamento
from fluxo.models import DocumentoDePagamento, Processo, TiposDeDocumento
from fluxo.utils import processar_pdf_comprovantes, split_pdf_to_temp_pages


logger = logging.getLogger(__name__)


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


@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
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
        except (PyPDF2.errors.PdfReadError, OSError, TypeError, ValueError) as exc:
            logger.exception("Erro ao fatiar comprovantes (modo=%s)", modo)
            return JsonResponse({"sucesso": False, "erro": str(exc)})
    return JsonResponse({"sucesso": False, "erro": "Arquivo não enviado."})


@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
def api_vincular_comprovantes(request):
    if request.method == "POST":
        processo_id = None
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
                except (FileNotFoundError, OSError) as exc:
                    logger.warning("Falha ao remover arquivo temporário %s: %s", temp_path, exc)

            return JsonResponse(
                {
                    "sucesso": True,
                    "mensagem": f'Processo #{processo_id} baixado com sucesso! Status alterado para "PAGO - EM CONFERÊNCIA".',
                }
            )
        except json.JSONDecodeError:
            return JsonResponse({"sucesso": False, "erro": "JSON inválido no corpo da requisição."})
        except (OSError, TypeError, ValueError) as exc:
            logger.exception("Erro ao vincular comprovantes no processo %s", processo_id)
            return JsonResponse({"sucesso": False, "erro": str(exc)})

    return JsonResponse({"sucesso": False, "erro": "Método inválido."})


__all__ = ["serializar_comprovante", "api_fatiar_comprovantes", "api_vincular_comprovantes"]
