"""Serviços fiscais para anexação documental e relatório mensal de retenções."""

import csv
import io
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

from django.apps import apps
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import F
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from pagamentos.domain_models import TiposDeDocumento, TiposDePagamento

if TYPE_CHECKING:
    from fiscal.models import RetencaoImposto
    from pagamentos.domain_models import Processo

DOC_GUIA = "GUIA DE RECOLHIMENTO DE IMPOSTOS"
DOC_COMPROVANTE = "COMPROVANTE DE RECOLHIMENTO DE IMPOSTOS"
DOC_RELATORIO = "RELATÓRIO MENSAL DE RETENÇÕES"
DOC_RELATORIO_AGRUPAMENTO = "RELATÓRIO DE RETENÇÕES AGRUPADAS"


def _get_tipo_documento_impostos(nome_tipo: str) -> TiposDeDocumento:
    tipo_pagamento_impostos, _ = TiposDePagamento.objects.get_or_create(
        tipo_de_pagamento__iexact="IMPOSTOS",
        defaults={"tipo_de_pagamento": "IMPOSTOS"},
    )
    tipo_documento, _ = TiposDeDocumento.objects.get_or_create(
        tipo_de_documento__iexact=nome_tipo,
        tipo_de_pagamento=tipo_pagamento_impostos,
        defaults={"tipo_de_documento": nome_tipo},
    )
    return tipo_documento


def gerar_relatorio_retencoes_mensal_csv(retencoes: list, mes: int, ano: int) -> bytes:
    """Gera relatório CSV consolidado por código de imposto para competência mensal."""
    saida = io.StringIO()
    writer = csv.writer(saida, delimiter=";")

    writer.writerow(["RELATORIO MENSAL DE RETENCOES"])
    writer.writerow(["Competencia", f"{mes:02d}/{ano}"])
    writer.writerow([])
    writer.writerow(["Codigo", "Qtde Retencoes", "Base Calculo Total", "Valor Retido Total"])

    agregado = defaultdict(lambda: {"qtd": 0, "base": Decimal("0"), "valor": Decimal("0")})

    for retencao in retencoes:
        codigo = (retencao.codigo.codigo or "SEM_CODIGO").strip()
        agregado[codigo]["qtd"] += 1
        agregado[codigo]["base"] += retencao.rendimento_tributavel or Decimal("0")
        agregado[codigo]["valor"] += retencao.valor or Decimal("0")

    for codigo in sorted(agregado.keys()):
        writer.writerow(
            [
                codigo,
                agregado[codigo]["qtd"],
                f"{agregado[codigo]['base']:.2f}",
                f"{agregado[codigo]['valor']:.2f}",
            ]
        )

    writer.writerow([])
    writer.writerow(["Detalhamento"])
    writer.writerow(
        [
            "RetencaoID",
            "ProcessoPagamentoID",
            "Codigo",
            "NF",
            "Competencia",
            "BaseCalculo",
            "ValorRetido",
        ]
    )

    for retencao in sorted(retencoes, key=lambda item: item.id):
        writer.writerow(
            [
                retencao.id,
                retencao.processo_pagamento_id,
                retencao.codigo.codigo if retencao.codigo else "",
                retencao.nota_fiscal.numero_nota_fiscal if retencao.nota_fiscal else "",
                retencao.competencia.strftime("%m/%Y") if retencao.competencia else "",
                f"{(retencao.rendimento_tributavel or Decimal('0')):.2f}",
                f"{(retencao.valor or Decimal('0')):.2f}",
            ]
        )

    return saida.getvalue().encode("utf-8-sig")


def _format_decimal(value) -> str:
    valor = value if value is not None else Decimal("0")
    return f"{valor:.2f}"


def gerar_relatorio_retencoes_agrupamento_pdf(retencoes: list["RetencaoImposto"], processo_id: int) -> bytes:
    """Gera PDF com todas as colunas canônicas das retenções agrupadas."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    margem_esquerda = 36
    linha = page_height - 40
    passo = 14

    def _nova_pagina_se_necessario():
        nonlocal linha
        if linha <= 48:
            pdf.showPage()
            linha = page_height - 40

    def _escrever(texto: str, negrito: bool = False):
        nonlocal linha
        _nova_pagina_se_necessario()
        pdf.setFont("Helvetica-Bold" if negrito else "Helvetica", 9)
        texto_normalizado = str(texto)
        try:
            pdf.drawString(margem_esquerda, linha, texto_normalizado)
        except Exception as exc:
            raise ValueError("Falha ao renderizar conteúdo textual no relatório PDF de retenções.") from exc
        linha -= passo

    _escrever(f"RELATÓRIO DE RETENÇÕES AGRUPADAS - PROCESSO #{processo_id}", negrito=True)
    _escrever(f"Quantidade de retenções: {len(retencoes)}")
    _escrever(
        "Campos: id, nota_fiscal, beneficiario, rendimento_tributavel, data_pagamento, codigo, valor, status, processo_pagamento, competencia"
    )
    linha -= 4

    for indice, retencao in enumerate(sorted(retencoes, key=lambda item: item.id), start=1):
        nota_fiscal = getattr(retencao, "nota_fiscal", None)
        beneficiario = getattr(retencao, "beneficiario", None)
        codigo = getattr(retencao, "codigo", None)
        status = getattr(retencao, "status", None)

        _escrever(f"Retenção {indice}", negrito=True)
        _escrever(f"id: {retencao.id}")
        _escrever(f"nota_fiscal: {retencao.nota_fiscal_id or ''}")
        _escrever(f"nota_fiscal.numero_nota_fiscal: {getattr(nota_fiscal, 'numero_nota_fiscal', '')}")
        _escrever(f"nota_fiscal.processo_id: {getattr(nota_fiscal, 'processo_id', '')}")
        _escrever(f"beneficiario: {retencao.beneficiario_id or ''}")
        _escrever(f"beneficiario.nome: {getattr(beneficiario, 'nome', '')}")
        _escrever(f"rendimento_tributavel: {_format_decimal(retencao.rendimento_tributavel)}")
        _escrever(f"data_pagamento: {retencao.data_pagamento.isoformat() if retencao.data_pagamento else ''}")
        _escrever(f"codigo: {retencao.codigo_id or ''}")
        _escrever(f"codigo.codigo: {getattr(codigo, 'codigo', '')}")
        _escrever(f"valor: {_format_decimal(retencao.valor)}")
        _escrever(f"status: {retencao.status_id or ''}")
        _escrever(f"status.status_choice: {getattr(status, 'status_choice', '')}")
        _escrever(f"processo_pagamento: {retencao.processo_pagamento_id or ''}")
        _escrever(f"competencia: {retencao.competencia.isoformat() if retencao.competencia else ''}")
        linha -= 4

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def anexar_relatorio_agrupamento_retencoes_no_processo(
    processo: "Processo",
    retencoes: list["RetencaoImposto"],
):
    """Anexa relatório PDF do agrupamento na ordem 1 do processo informado."""
    if not retencoes:
        return None

    DocumentoProcesso = apps.get_model("pagamentos", "DocumentoProcesso")
    tipo_relatorio = _get_tipo_documento_impostos(DOC_RELATORIO_AGRUPAMENTO)
    pdf_bytes = gerar_relatorio_retencoes_agrupamento_pdf(retencoes, processo.id)

    processo.documentos.all().update(ordem=F("ordem") + 1)
    return DocumentoProcesso.objects.create(
        processo=processo,
        arquivo=ContentFile(pdf_bytes, name=f"relatorio_retencoes_agrupadas_proc_{processo.id}.pdf"),
        tipo=tipo_relatorio,
        ordem=1,
    )


def anexar_guia_comprovante_relatorio_em_processos(
    retencoes: list,
    guia_bytes: bytes,
    guia_nome: str,
    comprovante_bytes: bytes,
    comprovante_nome: str,
    mes: int,
    ano: int,
) -> int:
    """Anexa guia, comprovante e relatório mensal em cada processo de recolhimento envolvido."""
    DocumentoProcesso = apps.get_model("pagamentos", "DocumentoProcesso")
    processo_ids = sorted({retencao.processo_pagamento_id for retencao in retencoes if retencao.processo_pagamento_id})
    if not processo_ids:
        return 0

    tipo_guia = _get_tipo_documento_impostos(DOC_GUIA)
    tipo_comprovante = _get_tipo_documento_impostos(DOC_COMPROVANTE)
    tipo_relatorio = _get_tipo_documento_impostos(DOC_RELATORIO)

    relatorio_bytes = gerar_relatorio_retencoes_mensal_csv(retencoes, mes, ano)

    total_processos = 0
    with transaction.atomic():
        for processo_id in processo_ids:
            processo_referencia = next(
                (retencao.processo_pagamento for retencao in retencoes if retencao.processo_pagamento_id == processo_id),
                None,
            )
            if processo_referencia is None:
                continue

            DocumentoProcesso.objects.create(
                processo=processo_referencia,
                arquivo=ContentFile(guia_bytes, name=f"guia_proc_{processo_id}_{guia_nome}"),
                tipo=tipo_guia,
                ordem=97,
            )
            DocumentoProcesso.objects.create(
                processo=processo_referencia,
                arquivo=ContentFile(comprovante_bytes, name=f"comprovante_proc_{processo_id}_{comprovante_nome}"),
                tipo=tipo_comprovante,
                ordem=98,
            )
            DocumentoProcesso.objects.create(
                processo=processo_referencia,
                arquivo=ContentFile(relatorio_bytes, name=f"relatorio_retencoes_{mes:02d}_{ano}_proc_{processo_id}.csv"),
                tipo=tipo_relatorio,
                ordem=99,
            )
            total_processos += 1

    return total_processos


def criar_documentos_pagamento_impostos(
    retencoes: list,
    relatorio_bytes: bytes,
    relatorio_nome: str,
    guia_bytes: bytes,
    guia_nome: str,
    comprovante_bytes: bytes,
    comprovante_nome: str,
    competencia,
) -> list:
    """Cria um DocumentoPagamentoImposto por retenção selecionada, retornando os objetos criados.

    Idempotente: se já existir documento para a combinação retencao/codigo/competencia, ignora.
    """
    from fiscal.models import DocumentoPagamentoImposto
    from django.core.files.base import ContentFile
    from datetime import date as _date

    competencia_normalizada = _date(competencia.year, competencia.month, 1)
    criados = []

    with transaction.atomic():
        for retencao in retencoes:
            _, created = DocumentoPagamentoImposto.objects.get_or_create(
                retencao=retencao,
                codigo_imposto=retencao.codigo,
                competencia=competencia_normalizada,
                defaults={
                    'relatorio_retencoes': ContentFile(
                        relatorio_bytes,
                        name=f"relatorio_{retencao.id}_{relatorio_nome}",
                    ),
                    'guia_recolhimento': ContentFile(
                        guia_bytes,
                        name=f"guia_{retencao.id}_{guia_nome}",
                    ),
                    'comprovante_pagamento': ContentFile(
                        comprovante_bytes,
                        name=f"comprovante_{retencao.id}_{comprovante_nome}",
                    ),
                },
            )
            if created:
                criados.append(retencao.id)

    return criados


def verificar_completude_documentos_impostos(processo) -> list:
    """Verifica se todas as retenções vinculadas ao processo possuem DocumentoPagamentoImposto completo.

    Retorna lista de IDs de retenções pendentes. Lista vazia = processo completo.
    """
    from fiscal.models import DocumentoPagamentoImposto

    retencoes = list(
        processo.impostos_recolhidos.select_related('codigo').all()
    )
    if not retencoes:
        return []

    retencao_ids = [r.id for r in retencoes]
    docs_completos = set(
        DocumentoPagamentoImposto.objects.filter(
            retencao_id__in=retencao_ids,
            relatorio_retencoes__isnull=False,
            guia_recolhimento__isnull=False,
            comprovante_pagamento__isnull=False,
        )
        .exclude(relatorio_retencoes="")
        .exclude(guia_recolhimento="")
        .exclude(comprovante_pagamento="")
        .values_list("retencao_id", flat=True)
    )
    return [retencao.id for retencao in retencoes if retencao.id not in docs_completos]


__all__ = [
    "anexar_relatorio_agrupamento_retencoes_no_processo",
    "anexar_guia_comprovante_relatorio_em_processos",
    "gerar_relatorio_retencoes_agrupamento_pdf",
    "gerar_relatorio_retencoes_mensal_csv",
    "criar_documentos_pagamento_impostos",
    "verificar_completude_documentos_impostos",
]
