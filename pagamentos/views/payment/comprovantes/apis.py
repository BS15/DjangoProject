"""Endpoints API da etapa de comprovantes de pagamento."""

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
from django.views.decorators.http import require_POST

from pagamentos.domain_models.documentos import ComprovanteDePagamento
from pagamentos.domain_models import DocumentoProcesso, Processo, ProcessoStatus, TiposDeDocumento
from commons.shared.pdf_tools import split_pdf_to_temp_pages
from .helpers import processar_pdf_comprovantes
from .actions import vincular_comprovantes_action as api_vincular_comprovantes


logger = logging.getLogger(__name__)


def serializar_comprovante(comp):
    """Converte o resultado de um comprovante para estrutura serializável em JSON."""
    return {
        **comp,
        "cpf_cnpj_encontrados": [
            {"cpf_cnpj": item["cpf_cnpj"], "credor": getattr(item["credor"], "nome", None)}
            for item in comp.get("cpf_cnpj_encontrados", [])
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


@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
@require_POST
def api_fatiar_comprovantes(request):
    if request.FILES.get("pdf_banco"):
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


__all__ = ["serializar_comprovante", "api_fatiar_comprovantes", "api_vincular_comprovantes"]
