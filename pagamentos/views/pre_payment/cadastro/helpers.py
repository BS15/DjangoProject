"""Helpers de ingestão de documentos na etapa de cadastro pré-pagamento."""

import re

import PyPDF2


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


__all__ = ["processar_pdf_boleto"]
