"""Serviços fiscais para anexação documental e orquestração de retenções."""

from typing import TYPE_CHECKING

from django.apps import apps
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import F

from fiscal.services.impostos_relatorios import (
    gerar_relatorio_retencoes_agrupamento_pdf,
    gerar_relatorio_retencoes_mensal_csv,
)
from pagamentos.domain_models import TiposDeDocumento, TiposDePagamento

if TYPE_CHECKING:
    from fiscal.models import RetencaoImposto
    from pagamentos.domain_models import Processo

DOC_GUIA = "GUIA DE RECOLHIMENTO DE IMPOSTOS"
DOC_COMPROVANTE = "COMPROVANTE DE RECOLHIMENTO DE IMPOSTOS"
DOC_RELATORIO = "RELATÓRIO MENSAL DE RETENÇÕES"
DOC_RELATORIO_AGRUPAMENTO = "RELATÓRIO DE RETENÇÕES AGRUPADAS"


def _get_tipo_documento_impostos(nome_tipo: str) -> TiposDeDocumento:
    """Obtém ou cria o tipo de documento de imposto pelo nome, vinculado ao tipo de pagamento 'IMPOSTOS'."""
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


def agrupar_retencoes_em_processo_recolhimento(retencao_ids: list[str]):
    """Agrupa retenções elegíveis e cria processo de recolhimento com relatório anexado."""
    RetencaoImposto = apps.get_model("fiscal", "RetencaoImposto")
    Credor = apps.get_model("credores", "Credor")
    Processo = apps.get_model("pagamentos", "Processo")
    StatusChoicesProcesso = apps.get_model("pagamentos", "StatusChoicesProcesso")

    with transaction.atomic():
        retencoes = list(
            RetencaoImposto.objects.select_for_update()
            .select_related("codigo", "status", "beneficiario", "nota_fiscal")
            .filter(id__in=retencao_ids, processo_pagamento__isnull=True)
        )

        if not retencoes:
            return None

        total_impostos = sum((retencao.valor or 0) for retencao in retencoes)
        if total_impostos <= 0:
            raise ValueError("Os itens selecionados não possuem valores válidos.")

        status_padrao, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact="A PAGAR - PENDENTE AUTORIZAÇÃO",
            defaults={"status_choice": "A PAGAR - PENDENTE AUTORIZAÇÃO"},
        )

        credor_orgao, _ = Credor.objects.get_or_create(
            nome="Órgão Arrecadador (A Definir)",
            defaults={"nome": "Órgão Arrecadador (A Definir)"},
        )

        tipo_pagamento_impostos, _ = TiposDePagamento.objects.get_or_create(
            tipo_de_pagamento="IMPOSTOS"
        )

        novo_processo = Processo.objects.create(
            credor=credor_orgao,
            valor_bruto=total_impostos,
            valor_liquido=total_impostos,
            detalhamento="Pagamento Agrupado de Impostos Retidos",
            observacao="Gerado automaticamente.",
            status=status_padrao,
            tipo_pagamento=tipo_pagamento_impostos,
        )

        for retencao in retencoes:
            retencao.processo_pagamento = novo_processo
            retencao.save(update_fields=["processo_pagamento"])

        anexar_relatorio_agrupamento_retencoes_no_processo(
            processo=novo_processo,
            retencoes=retencoes,
        )

    return novo_processo


def anexar_documentos_competencia_retencoes(
    retencao_ids: list[str],
    guia_bytes: bytes,
    guia_nome: str,
    comprovante_bytes: bytes,
    comprovante_nome: str,
    mes: int,
    ano: int,
) -> int:
    """Anexa guia, comprovante e relatório mensal para retenções elegíveis por competência."""
    RetencaoImposto = apps.get_model("fiscal", "RetencaoImposto")

    with transaction.atomic():
        retencoes = list(
            RetencaoImposto.objects.select_for_update()
            .select_related("processo_pagamento", "codigo", "nota_fiscal")
            .filter(id__in=retencao_ids, competencia__month=mes, competencia__year=ano)
            .exclude(processo_pagamento__isnull=True)
        )

        if not retencoes:
            return 0

        return anexar_guia_comprovante_relatorio_em_processos(
            retencoes=retencoes,
            guia_bytes=guia_bytes,
            guia_nome=guia_nome,
            comprovante_bytes=comprovante_bytes,
            comprovante_nome=comprovante_nome,
            mes=mes,
            ano=ano,
        )


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
    "agrupar_retencoes_em_processo_recolhimento",
    "anexar_documentos_competencia_retencoes",
    "criar_documentos_pagamento_impostos",
    "verificar_completude_documentos_impostos",
]
