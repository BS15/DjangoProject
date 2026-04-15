"""Endpoints API da etapa de contas a pagar."""

import logging

from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from fluxo.domain_models import Processo
logger = logging.getLogger(__name__)


@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
def api_extrair_codigos_barras_processo(request, pk):
    """Retorna códigos de barras já persistidos nos documentos de um processo."""
    processo = get_object_or_404(Processo, id=pk)
    boleto_docs_qs = processo.documentos.select_related("tipo").filter(
        tipo__tipo_de_documento__icontains="boleto"
    )
    barcodes = [doc.codigo_barras for doc in boleto_docs_qs if doc.codigo_barras]
    return JsonResponse(
        {
            "sucesso": True,
            "processo_id": processo.id,
            "n_documentos_boleto": boleto_docs_qs.count(),
            "n_extraidos": len(barcodes),
            "barcodes": barcodes,
        }
    )


__all__ = [
    "api_extrair_codigos_barras_processo",
]
