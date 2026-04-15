"""Helpers de parsing para uploads de boleto e comprovantes de pagamento."""

import re

import pdfplumber
from commons.shared.pdf_tools import split_pdf_to_temp_pages
from commons.shared.text_tools import normalize_account, normalize_document
from django.core.files.storage import default_storage


def _extract_comprovante_fields(texto_flat):
    """Extrai campos estruturados de um texto de comprovante bancário."""
    padrao_valor = re.compile(
        r"(?:VALOR TOTAL|VALOR DO DOCUMENTO|VALOR COBRADO|VALOR EM DINHEIRO|VALOR)\s*:?\s*(?:R\$\s*)?([\d.,]+)",
        re.IGNORECASE,
    )

    valor_float = 0.00
    for match_valor in padrao_valor.finditer(texto_flat):
        valor_str = match_valor.group(1).replace(".", "").replace(",", ".")
        try:
            valor_float = float(valor_str)
            break
        except ValueError:
            pass

    cpf_cnpj = re.findall(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2}", texto_flat)
    contas = re.findall(r"AGENCIA:\s*([\d-]+)\s*CONTA:\s*([\d.-]+[Xx]?)", texto_flat)

    data_pagamento = ""
    match_data = re.search(
        r"(?:DATA(?:\s*DO PAGAMENTO|\s*DA TRANSFERENCIA)?|DEBITO EM)\s*:?\s*(\d{2}/\d{2}/\d{4})",
        texto_flat,
        re.IGNORECASE,
    )
    if match_data:
        partes = match_data.group(1).split("/")
        if len(partes) == 3:
            data_pagamento = f"{partes[2]}-{partes[1]}-{partes[0]}"

    numero_comprovante = ""
    autenticacao_match = re.search(
        r"NR\.AUTENTICACAO\s*([A-Z0-9]\.[A-Z0-9]{3}\.[A-Z0-9]{3}\.[A-Z0-9]{3}\.[A-Z0-9]{3}\.[A-Z0-9]{3})",
        texto_flat,
        re.IGNORECASE,
    )
    if autenticacao_match:
        numero_comprovante = autenticacao_match.group(1)

    return {
        "valor_extraido": valor_float,
        "cpf_cnpj": cpf_cnpj,
        "contas": contas,
        "data_pagamento": data_pagamento,
        "numero_comprovante": numero_comprovante,
    }


def _match_credor_por_cpf_cnpj(cpf_cnpj_list, cnpj_orgao_norm, Credor):
    """Relaciona CPF/CNPJ extraído ao credor cadastrado, ignorando o órgão."""
    credor_encontrado = None
    cpf_cnpj_encontrados = []

    for cpf_cnpj in cpf_cnpj_list:
        cpf_cnpj_norm = normalize_document(cpf_cnpj)
        if cpf_cnpj_norm and cpf_cnpj_norm != cnpj_orgao_norm:
            credor = Credor.objects.filter(cpf_cnpj=cpf_cnpj).first()
            cpf_cnpj_encontrados.append({"cpf_cnpj": cpf_cnpj, "credor": credor})
            if credor and not credor_encontrado:
                credor_encontrado = credor

    return credor_encontrado, cpf_cnpj_encontrados


def _match_credor_por_contas(contas, agencia_orgao_norm, conta_orgao_norm, ContasBancarias):
    """Relaciona agência/conta extraídas ao titular cadastrado, excluindo conta do órgão."""
    credor_encontrado = None
    contas_encontradas = []

    for agencia, conta in contas:
        agencia_norm, conta_norm = normalize_account(agencia, conta)
        if agencia_norm != agencia_orgao_norm or conta_norm != conta_orgao_norm:
            conta_db = ContasBancarias.objects.filter(agencia=agencia, conta=conta_norm).first()
            titular = conta_db.titular if conta_db else None
            contas_encontradas.append({"agencia": agencia, "conta": conta_norm, "credor": titular})
            if titular and not credor_encontrado:
                credor_encontrado = titular

    return credor_encontrado, contas_encontradas


def processar_pdf_comprovantes(pdf_file):
    """Processa comprovantes em PDF e retorna dados extraídos por página."""
    from credores.models import Credor, ContasBancarias

    cnpj_orgao = "82.894.098/0001-32"
    agencia_orgao = "3582-3"
    conta_orgao_limpa = "7429-2"

    cnpj_orgao_norm = normalize_document(cnpj_orgao)
    agencia_orgao_norm, conta_orgao_norm = normalize_account(agencia_orgao, conta_orgao_limpa)

    paginas_temp = split_pdf_to_temp_pages(pdf_file)
    resultados = []

    for pagina_info in paginas_temp:
        with default_storage.open(pagina_info["temp_path"], "rb") as arquivo_temp:
            with pdfplumber.open(arquivo_temp) as pdf_leitor:
                texto = pdf_leitor.pages[0].extract_text() or ""

        texto_flat = re.sub(r"\s+", " ", texto)
        campos_extraidos = _extract_comprovante_fields(texto_flat)

        credor_por_cpf_cnpj, cpf_cnpj_encontrados = _match_credor_por_cpf_cnpj(
            campos_extraidos["cpf_cnpj"],
            cnpj_orgao_norm,
            Credor,
        )
        credor_por_conta, contas_encontradas = _match_credor_por_contas(
            campos_extraidos["contas"],
            agencia_orgao_norm,
            conta_orgao_norm,
            ContasBancarias,
        )
        credor_encontrado = credor_por_cpf_cnpj or credor_por_conta

        resultados.append(
            {
                **pagina_info,
                "credor_extraido": credor_encontrado.nome if credor_encontrado else None,
                "valor_extraido": campos_extraidos["valor_extraido"],
                "data_pagamento": campos_extraidos["data_pagamento"],
                "numero_comprovante": campos_extraidos["numero_comprovante"],
                "cpf_cnpj_encontrados": cpf_cnpj_encontrados,
                "contas_encontradas": contas_encontradas,
            }
        )
    return resultados


__all__ = [
    "processar_pdf_comprovantes",
]