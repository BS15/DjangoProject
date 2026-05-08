"""Endpoints API da etapa de empenho."""

import logging

import PyPDF2
from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse

from .helpers import extract_siscac_data


logger = logging.getLogger(__name__)


@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def api_extrair_dados_empenho(request):
    """Extrai número e data de empenho a partir de PDF SISCAC enviado pelo usuário."""
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "erro": "Método não permitido."}, status=405)

    siscac_file = request.FILES.get("siscac_file")
    if not siscac_file:
        return JsonResponse({"sucesso": False, "erro": "Nenhum arquivo enviado."}, status=400)

    try:
        data = extract_siscac_data(siscac_file)
    except (PyPDF2.errors.PdfReadError, OSError, TypeError, ValueError):
        logger.exception(
            "Erro ao extrair dados de empenho do arquivo %s", getattr(siscac_file, "name", "")
        )
        return JsonResponse(
            {
                "sucesso": False,
                "erro": "Erro ao processar o arquivo. Verifique se é um PDF SISCAC válido.",
            },
            status=500,
        )

    n_nota_empenho = data.get("n_nota_empenho") or ""
    data_empenho = data.get("data_empenho")
    ano_exercicio = data.get("ano_exercicio")
    data_empenho_iso = data_empenho if data_empenho else ""

    if not n_nota_empenho and not data_empenho_iso:
        return JsonResponse(
            {
                "sucesso": False,
                "erro": "Não foi possível extrair dados de empenho do arquivo. Verifique se é um documento SISCAC válido.",
            },
            status=422,
        )

    return JsonResponse(
        {
            "sucesso": True,
            "n_nota_empenho": n_nota_empenho,
            "data_empenho": data_empenho_iso,
            "ano_exercicio": ano_exercicio,
        }
    )


__all__ = ["api_extrair_dados_empenho"]
