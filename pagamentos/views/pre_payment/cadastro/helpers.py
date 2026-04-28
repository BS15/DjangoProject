"""Helpers compartilhados da etapa de cadastro pré-pagamento."""

import re
from typing import Optional

import PyPDF2
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404

from pagamentos.domain_models import Processo

from ..helpers import _validar_regras_edicao_processo


def get_status_inicial(processo: Processo) -> str:
    """Normaliza o status textual do processo para uso nas guards da UI."""
    return processo.status.opcao_status.upper() if processo.status else ""


def obter_contexto_edicao(
    request: HttpRequest,
    pk: int,
) -> tuple[Processo, str, Optional[HttpResponse], bool]:
    """Carrega processo e aplica as regras de guarda compartilhadas da edição."""
    processo = get_object_or_404(Processo, id=pk)
    status_inicial = get_status_inicial(processo)
    redirecionamento, somente_documentos = _validar_regras_edicao_processo(request, processo, status_inicial)
    return processo, status_inicial, redirecionamento, somente_documentos


def processar_pdf_boleto(pdf_file):
    """Localiza linha digitável válida em PDF de boleto/arrecadação."""
    leitor = PyPDF2.PdfReader(pdf_file)
    texto = " ".join([pagina.extract_text() for pagina in leitor.pages if pagina.extract_text()])
    texto = re.sub(r"\s+", " ", texto)

    padrao = r"(?<!\d)(?:\d[\s\.\-]*){47,55}(?!\d)"
    candidatos = re.findall(padrao, texto)

    for candidato in candidatos:
        numeros = re.sub(r"\D", "", candidato)

        codigo_encontrado = None
        if len(numeros) == 48 and numeros.startswith("8"):
            codigo_encontrado = numeros
        elif len(numeros) == 47:
            codigo_encontrado = numeros
        elif 47 < len(numeros) <= 55:
            codigo_encontrado = numeros[-47:]

        if codigo_encontrado:
            return {
                "codigo_barras": codigo_encontrado,
                "valor": 0,
                "vencimento": "",
            }

    raise ValueError("Linha digitavel valida nao encontrada no PDF.")


__all__ = ["get_status_inicial", "obter_contexto_edicao", "processar_pdf_boleto"]
