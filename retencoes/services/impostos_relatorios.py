"""Geradores de relatorios para retencoes de impostos."""

from __future__ import annotations

import csv
from io import BytesIO, StringIO

from reportlab.pdfgen import canvas


def _stringify_value(value):
    """Converte valores para string previsivel em relatorios textuais."""
    if value is None:
        return ""
    return str(value)


def gerar_relatorio_retencoes_agrupamento_pdf(retencoes, processo_id):
    """Gera PDF simples com o espelho textual das retencoes agrupadas."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)

    linhas = [
        "RELATORIO DE RETENCOES AGRUPADAS",
        f"processo_id: {processo_id}",
        "id, nota_fiscal, beneficiario, rendimento_tributavel, data_pagamento, codigo, valor, status, processo_pagamento, competencia",
    ]

    for retencao in retencoes:
        nota_fiscal = getattr(retencao, "nota_fiscal_id", None)
        beneficiario = ""
        nota_obj = getattr(retencao, "nota_fiscal", None)
        if nota_obj is not None and getattr(nota_obj, "beneficiario", None) is not None:
            beneficiario = getattr(nota_obj.beneficiario, "nome", "")

        codigo_obj = getattr(retencao, "codigo", None)
        codigo_val = getattr(codigo_obj, "codigo", "") if codigo_obj is not None else ""

        status_obj = getattr(retencao, "status", None)
        status_val = getattr(status_obj, "nome", "") if status_obj is not None else ""

        linhas.extend(
            [
                f"id: {retencao.id}",
                f"nota_fiscal: {nota_fiscal}",
                f"beneficiario: {beneficiario}",
                f"rendimento_tributavel: {_stringify_value(getattr(retencao, 'rendimento_tributavel', None))}",
                f"data_pagamento: {_stringify_value(getattr(retencao, 'data_pagamento', None))}",
                f"codigo.codigo: {codigo_val}",
                f"valor: {_stringify_value(getattr(retencao, 'valor', None))}",
                f"status: {status_val}",
                f"processo_pagamento: {_stringify_value(getattr(retencao, 'processo_pagamento_id', None))}",
                f"competencia: {_stringify_value(getattr(retencao, 'competencia', None))}",
                "",
            ]
        )

    y = 800
    for linha in linhas:
        if y < 40:
            pdf.showPage()
            y = 800
        pdf.drawString(36, y, linha[:160])
        y -= 14

    pdf.save()
    return buffer.getvalue()


def gerar_relatorio_retencoes_mensal_csv(retencoes, mes, ano):
    """Gera CSV mensal de retencoes para anexacao documental."""
    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["mes", "ano", "retencao_id", "nota_fiscal_id", "codigo", "valor", "competencia", "processo_pagamento_id"])

    for retencao in retencoes:
        codigo_obj = getattr(retencao, "codigo", None)
        writer.writerow(
            [
                mes,
                ano,
                getattr(retencao, "id", ""),
                getattr(retencao, "nota_fiscal_id", ""),
                getattr(codigo_obj, "codigo", "") if codigo_obj is not None else "",
                _stringify_value(getattr(retencao, "valor", None)),
                _stringify_value(getattr(retencao, "competencia", None)),
                getattr(retencao, "processo_pagamento_id", ""),
            ]
        )

    return output.getvalue().encode("utf-8")


__all__ = [
    "gerar_relatorio_retencoes_agrupamento_pdf",
    "gerar_relatorio_retencoes_mensal_csv",
]
