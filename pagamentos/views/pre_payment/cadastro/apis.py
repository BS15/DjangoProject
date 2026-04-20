"""Endpoints API da etapa de cadastro pré-pagamento."""

import json
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import PyPDF2
from django.db import DatabaseError
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.contrib.auth.decorators import permission_required
from django.views.decorators.http import require_POST

from .helpers import processar_pdf_boleto
from .actions import (
    toggle_documento_fiscal_action as api_toggle_documento_fiscal,
    salvar_nota_fiscal_action as api_salvar_nota_fiscal,
)

logger = logging.getLogger(__name__)

from credores.models import Credor
from fiscal.models import DocumentoFiscal, RetencaoImposto
from pagamentos.domain_models import Boleto_Bancario, Pendencia, Processo, StatusChoicesPendencias, TiposDeDocumento, TiposDePendencias
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from .actions import _status_bloqueia_gestao_fiscal


@permission_required("pagamentos.pode_operar_contas_pagar", raise_exception=True)
def api_tipos_documento_por_pagamento(request):
    """Lista tipos de documento ativos vinculados a um tipo de pagamento."""
    tipo_pagamento_id = request.GET.get("tipo_pagamento_id")

    if not tipo_pagamento_id:
        return JsonResponse({"sucesso": False, "erro": "ID não fornecido"})

    try:
        documentos_validos = (
            TiposDeDocumento.objects.filter(tipo_pagamento_id=tipo_pagamento_id, ativo=True)
            .values("id", "tipo_documento")
            .order_by("tipo_documento")
        )

        lista_docs = list(documentos_validos)
        return JsonResponse({"sucesso": True, "tipos": lista_docs})
    except (DatabaseError, TypeError, ValueError) as e:
        return JsonResponse({"sucesso": False, "erro": str(e)})


@permission_required("pagamentos.pode_operar_contas_pagar", raise_exception=True)
def api_extrair_codigos_barras_upload(request):
    """Extrai dados de boleto a partir de upload único ou em lote de PDFs.

    Endpoint de cadastro: usado durante o upload de documentos de boleto para
    pré-preencher o campo código de barras antes de salvar o documento.
    """
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "erro": "Método não permitido."}, status=405)

    files = request.FILES.getlist("boleto_files")
    if not files:
        single_file = (
            request.FILES.get("boleto_file")
            or request.FILES.get("boleto_pdf")
            or request.FILES.get("file")
        )
        if single_file:
            files = [single_file]

    if not files:
        return JsonResponse({"sucesso": False, "erro": "Nenhum arquivo enviado."}, status=400)

    if len(files) == 1:
        try:
            dados = processar_pdf_boleto(files[0]) or {}
        except (PyPDF2.errors.PdfReadError, OSError, TypeError, ValueError):
            logger.exception(
                "Erro ao processar boleto no upload %s", getattr(files[0], "name", "")
            )
            return JsonResponse(
                {
                    "sucesso": False,
                    "erro": "Erro ao processar boleto. Verifique se o arquivo é um PDF válido.",
                },
                status=500,
            )
        return JsonResponse({"sucesso": True, "dados": dados})

    barcodes = []
    n_extraidos = 0
    n_falhas = 0

    for pdf_file in files:
        try:
            dados = processar_pdf_boleto(pdf_file)
            codigo = dados.get("codigo_barras", "") if dados else ""
            if codigo:
                barcodes.append(codigo)
                n_extraidos += 1
            else:
                barcodes.append(None)
                n_falhas += 1
        except (PyPDF2.errors.PdfReadError, OSError, TypeError, ValueError):
            logger.exception(
                "Erro ao extrair código de barras de '%s'", getattr(pdf_file, "name", "arquivo")
            )
            barcodes.append(None)
            n_falhas += 1

    return JsonResponse(
        {
            "sucesso": True,
            "n_extraidos": n_extraidos,
            "n_falhas": n_falhas,
            "barcodes": [b for b in barcodes if b],
        }
    )


__all__ = [
    "api_tipos_documento_por_pagamento",
    "api_extrair_codigos_barras_upload",
    "api_toggle_documento_fiscal",
    "api_salvar_nota_fiscal",
]
