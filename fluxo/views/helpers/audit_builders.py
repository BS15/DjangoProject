"""Builders de payload para APIs de auditoria e historico do fluxo financeiro."""

import logging

from django.shortcuts import get_object_or_404
from django.urls import reverse

from fiscal.models import ComprovanteDePagamento, DocumentoFiscal, RetencaoImposto
from fluxo.models import (
    Devolucao,
    DocumentoDePagamento,
    Pendencia,
    Processo,
)
from fluxo.utils import format_br_date, format_brl_currency


logger = logging.getLogger(__name__)


def _aplicar_filtros_historico(qs, *, tipo_acao="", data_inicio="", data_fim="", usuario=""):
    """Aplica filtros de auditoria em queryset historico."""
    if tipo_acao:
        qs = qs.filter(history_type=tipo_acao)
    if data_inicio:
        qs = qs.filter(history_date__date__gte=data_inicio)
    if data_fim:
        qs = qs.filter(history_date__date__lte=data_fim)
    if usuario:
        qs = qs.filter(history_user__username__icontains=usuario)
    return qs


def _serializar_documentos_processo_auditoria(processo):
    """Serializa documentos de processo para consumo da API de auditoria."""
    documentos = processo.documentos.select_related("tipo").all().order_by("ordem")
    docs_list = []
    for doc in documentos:
        if not doc.arquivo:
            continue
        nome = doc.arquivo.name.split("/")[-1]
        docs_list.append(
            {
                "id": doc.id,
                "ordem": doc.ordem,
                "tipo": doc.tipo.tipo_de_documento if doc.tipo else "Documento",
                "nome": nome,
                "url": reverse("download_arquivo_seguro", args=["processo", doc.id]),
            }
        )
    return docs_list


def _serializar_pendencias_processo_auditoria(processo):
    """Serializa pendências do processo para visualização operacional."""
    pendencias_qs = processo.pendencias.select_related("status", "tipo").all()
    return [
        {
            "tipo": str(p.tipo),
            "descricao": p.descricao or "",
            "status": str(p.status) if p.status else "-",
        }
        for p in pendencias_qs
    ]


def _serializar_retencoes_processo_auditoria(processo):
    """Serializa retenções fiscais vinculadas às notas do processo."""
    retencoes_list = []
    notas = processo.notas_fiscais.prefetch_related("retencoes__status", "retencoes__codigo").all()
    for nf in notas:
        for ret in nf.retencoes.all():
            retencoes_list.append(
                {
                    "codigo": str(ret.codigo),
                    "valor": str(ret.valor),
                    "status": str(ret.status) if ret.status else "-",
                }
            )
    return retencoes_list


def _serializar_processo_base(processo):
    """Serializa campos centrais comuns do processo para reutilização em múltiplos payloads."""
    return {
        "processo_id": processo.id,
        "n_nota_empenho": processo.n_nota_empenho or str(processo.id),
        "credor_id": processo.credor_id,
        "credor": str(processo.credor) if processo.credor else "-",
        "valor_bruto": format_brl_currency(processo.valor_bruto),
        "valor_liquido": format_brl_currency(processo.valor_liquido),
        "data_empenho": format_br_date(processo.data_empenho),
        "data_vencimento": format_br_date(processo.data_vencimento),
        "data_pagamento": format_br_date(processo.data_pagamento),
        "status": str(processo.status) if processo.status else "-",
        "ano_exercicio": processo.ano_exercicio,
        "n_pagamento_siscac": processo.n_pagamento_siscac or "-",
        "forma_pagamento": str(processo.forma_pagamento) if processo.forma_pagamento else "-",
        "tipo_pagamento": str(processo.tipo_pagamento) if processo.tipo_pagamento else "-",
        "observacao": processo.observacao or "-",
        "conta": str(processo.conta) if processo.conta else "-",
        "detalhamento": processo.detalhamento or "-",
        "tag": str(processo.tag) if processo.tag else "-",
        "em_contingencia": processo.em_contingencia,
        "extraorcamentario": processo.extraorcamentario,
    }


def _build_payload_documentos_processo_auditoria(processo):
    """Monta payload completo de documentos/dados auxiliares de auditoria."""
    base = _serializar_processo_base(processo)
    return {
        **base,
        "pendencias": _serializar_pendencias_processo_auditoria(processo),
        "retencoes": _serializar_retencoes_processo_auditoria(processo),
        "documentos": _serializar_documentos_processo_auditoria(processo),
    }


def _build_payload_processo_detalhes(processo):
    """Monta payload padronizado de detalhes cadastrais de um processo."""
    return {
        "sucesso": True,
        "processo": _serializar_processo_base(processo),
    }


def _build_history_record(record, modelo_label):
    """Monta um registro de histórico enriquecido para exibição na interface.

    Resolve alterações em chaves estrangeiras para suas representações legíveis
    e normaliza valores booleanos e nulos antes de retornar o payload usado
    nas telas de auditoria.
    """
    from django.db.models import ForeignKey

    HISTORY_TYPE_LABELS = {"+": "Criação", "~": "Alteração", "-": "Exclusão"}
    changed_fields = []

    if record.history_type == "~":
        prev = record.prev_record
        if prev is not None:
            try:
                delta = record.diff_against(prev)
                model_fields = {f.name: f for f in record.instance._meta.get_fields()}

                for change in delta.changes:
                    field_name = change.field
                    old_val = change.old
                    new_val = change.new

                    field_obj = model_fields.get(field_name)
                    if isinstance(field_obj, ForeignKey):
                        related_model = field_obj.related_model

                        if old_val is not None:
                            try:
                                old_obj = related_model.objects.get(pk=old_val)
                                old_val = str(old_obj)
                            except related_model.DoesNotExist:
                                old_val = f"ID {old_val} (Excluído)"

                        if new_val is not None:
                            try:
                                new_obj = related_model.objects.get(pk=new_val)
                                new_val = str(new_obj)
                            except related_model.DoesNotExist:
                                new_val = f"ID {new_val} (Excluído)"

                    if isinstance(old_val, bool):
                        old_val = "Sim" if old_val else "Não"
                    if isinstance(new_val, bool):
                        new_val = "Sim" if new_val else "Não"

                    if old_val is None:
                        old_val = "N/A"
                    if new_val is None:
                        new_val = "N/A"

                    changed_fields.append(
                        {
                            "field": field_name.replace("_", " ").title(),
                            "old": old_val,
                            "new": new_val,
                        }
                    )
            except (AttributeError, TypeError, ValueError) as e:
                logger.warning("Falha ao montar diff de histórico para %s: %s", modelo_label, e)

    return {
        "modelo": modelo_label,
        "history_date": record.history_date,
        "history_user": record.history_user,
        "history_type": record.history_type,
        "history_type_label": HISTORY_TYPE_LABELS.get(record.history_type, record.history_type),
        "history_change_reason": getattr(record, "history_change_reason", None),
        "str_repr": str(record),
        "changed_fields": changed_fields,
    }


def _get_unified_history(pk):
    """Consolida o histórico do processo e dos modelos relacionados.

    Reúne eventos de auditoria do processo, documentos, pendências e notas
    fiscais, já enriquecidos para exibição e ordenados do mais recente para o
    mais antigo.
    """
    processo = get_object_or_404(Processo, id=pk)
    history_records = []

    for record in processo.history.all().select_related("history_user"):
        history_records.append(_build_history_record(record, "Processo"))
    for record in DocumentoDePagamento.history.filter(processo_id=pk).select_related("history_user"):
        history_records.append(_build_history_record(record, "Documento"))
    for record in Pendencia.history.filter(processo_id=pk).select_related("history_user"):
        history_records.append(_build_history_record(record, "Pendência"))
    for record in DocumentoFiscal.history.filter(processo_id=pk).select_related("history_user"):
        history_records.append(_build_history_record(record, "Nota Fiscal"))
    for record in RetencaoImposto.history.filter(nota_fiscal__processo_id=pk).select_related("history_user"):
        history_records.append(_build_history_record(record, "Retenção de Imposto"))
    for record in ComprovanteDePagamento.history.filter(processo_id=pk).select_related("history_user"):
        history_records.append(_build_history_record(record, "Comprovante de Pagamento"))
    for record in Devolucao.history.filter(processo_id=pk).select_related("history_user"):
        history_records.append(_build_history_record(record, "Devolução"))

    history_records.sort(key=lambda x: x["history_date"], reverse=True)
    return history_records


__all__ = [
    "_aplicar_filtros_historico",
    "_serializar_documentos_processo_auditoria",
    "_serializar_pendencias_processo_auditoria",
    "_serializar_retencoes_processo_auditoria",
    "_serializar_processo_base",
    "_build_payload_documentos_processo_auditoria",
    "_build_payload_processo_detalhes",
    "_build_history_record",
    "_get_unified_history",
]
