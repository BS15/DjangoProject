"""Views e APIs de auditoria/historico."""

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET

from ..models import (
    DocumentoAuxilio,
    DocumentoDiaria,
    DocumentoFiscal,
    DocumentoJeton,
    DocumentoProcesso,
    DocumentoReembolso,
    DocumentoSuprimentoDeFundos,
    Processo,
)
from .helpers import _build_history_record, _get_unified_history


@require_GET
@xframe_options_sameorigin
def api_documentos_processo(request, processo_id):
    processo = get_object_or_404(Processo, id=processo_id)
    documentos = processo.documentos.all().order_by("ordem")

    docs_list = []
    for doc in documentos:
        if doc.arquivo:
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

    pendencias_qs = processo.pendencias.select_related("status", "tipo").all()
    pendencias_list = [
        {
            "tipo": str(p.tipo),
            "descricao": p.descricao or "",
            "status": str(p.status) if p.status else "-",
        }
        for p in pendencias_qs
    ]

    retencoes_list = []
    for nf in processo.notas_fiscais.prefetch_related("retencoes__status", "retencoes__codigo").all():
        for ret in nf.retencoes.all():
            retencoes_list.append(
                {
                    "codigo": str(ret.codigo),
                    "valor": str(ret.valor),
                    "status": str(ret.status) if ret.status else "-",
                }
            )

    def fmt_date(d):
        return d.strftime("%d/%m/%Y") if d else "-"

    def fmt_decimal(v):
        if v is None:
            return "-"
        int_part, dec_part = f"{abs(v):.2f}".split(".")
        int_formatted = "{:,}".format(int(int_part)).replace(",", ".")
        signal = "-" if v < 0 else ""
        return f"R$ {signal}{int_formatted},{dec_part}"

    return JsonResponse(
        {
            "processo_id": processo.id,
            "n_nota_empenho": processo.n_nota_empenho or str(processo.id),
            "credor": str(processo.credor) if processo.credor else "-",
            "valor_bruto": fmt_decimal(processo.valor_bruto),
            "valor_liquido": fmt_decimal(processo.valor_liquido),
            "data_empenho": fmt_date(processo.data_empenho),
            "data_vencimento": fmt_date(processo.data_vencimento),
            "data_pagamento": fmt_date(processo.data_pagamento),
            "status": str(processo.status) if processo.status else "-",
            "pendencias": pendencias_list,
            "retencoes": retencoes_list,
            "documentos": docs_list,
        }
    )


def api_processo_detalhes(request):
    processo_id = request.GET.get("id", "").strip()
    if not processo_id:
        return JsonResponse({"sucesso": False, "erro": "ID do processo não informado."}, status=400)

    try:
        processo = Processo.objects.select_related(
            "credor", "forma_pagamento", "tipo_pagamento", "conta", "status", "tag"
        ).get(pk=processo_id)
    except Processo.DoesNotExist:
        return JsonResponse({"sucesso": False, "erro": f"Processo #{processo_id} não encontrado."}, status=404)
    except ValueError:
        return JsonResponse({"sucesso": False, "erro": "ID inválido."}, status=400)

    dados = {
        "sucesso": True,
        "processo": {
            "id": processo.pk,
            "n_nota_empenho": processo.n_nota_empenho or "—",
            "credor_id": processo.credor_id,
            "credor_nome": str(processo.credor) if processo.credor else "—",
            "data_empenho": str(processo.data_empenho) if processo.data_empenho else None,
            "valor_bruto": str(processo.valor_bruto) if processo.valor_bruto is not None else "0.00",
            "valor_liquido": str(processo.valor_liquido) if processo.valor_liquido is not None else "0.00",
            "ano_exercicio": processo.ano_exercicio,
            "n_pagamento_siscac": processo.n_pagamento_siscac or "—",
            "data_vencimento": str(processo.data_vencimento) if processo.data_vencimento else None,
            "data_pagamento": str(processo.data_pagamento) if processo.data_pagamento else None,
            "forma_pagamento": str(processo.forma_pagamento) if processo.forma_pagamento else "—",
            "tipo_pagamento": str(processo.tipo_pagamento) if processo.tipo_pagamento else "—",
            "observacao": processo.observacao or "—",
            "conta": str(processo.conta) if processo.conta else "—",
            "status": str(processo.status) if processo.status else "—",
            "detalhamento": processo.detalhamento or "—",
            "tag": str(processo.tag) if processo.tag else "—",
            "em_contingencia": processo.em_contingencia,
            "extraorcamentario": processo.extraorcamentario,
        },
    }
    return JsonResponse(dados)


def auditoria_view(request):
    HISTORY_TYPE_LABELS = {"+": "Criação", "~": "Alteração", "-": "Exclusão"}

    model_configs = [
        (Processo.history.model, "Processo"),
        (DocumentoProcesso.history.model, "Documento de Processo"),
        (DocumentoDiaria.history.model, "Documento de Diária"),
        (DocumentoReembolso.history.model, "Documento de Reembolso"),
        (DocumentoJeton.history.model, "Documento de Jeton"),
        (DocumentoAuxilio.history.model, "Documento de Auxílio"),
        (DocumentoSuprimentoDeFundos.history.model, "Documento de Suprimento"),
    ]

    modelo_filter = request.GET.get("modelo", "").strip()
    tipo_filter = request.GET.get("tipo_acao", "").strip()
    data_inicio = request.GET.get("data_inicio", "").strip()
    data_fim = request.GET.get("data_fim", "").strip()
    usuario_filter = request.GET.get("usuario", "").strip()

    all_records = []
    for history_model, label in model_configs:
        if modelo_filter and modelo_filter != label:
            continue
        qs = history_model.objects.select_related("history_user").all()
        if tipo_filter:
            qs = qs.filter(history_type=tipo_filter)
        if data_inicio:
            qs = qs.filter(history_date__date__gte=data_inicio)
        if data_fim:
            qs = qs.filter(history_date__date__lte=data_fim)
        if usuario_filter:
            qs = qs.filter(history_user__username__icontains=usuario_filter)
        for record in qs:
            all_records.append(
                {
                    "modelo": label,
                    "object_id": record.id,
                    "history_date": record.history_date,
                    "history_user": record.history_user,
                    "history_type": record.history_type,
                    "history_type_label": HISTORY_TYPE_LABELS.get(record.history_type, record.history_type),
                    "history_change_reason": getattr(record, "history_change_reason", None),
                    "str_repr": str(record),
                }
            )

    all_records.sort(key=lambda x: x["history_date"], reverse=True)
    total = len(all_records)
    all_records = all_records[:500]

    context = {
        "registros": all_records,
        "total": total,
        "modelos_disponiveis": [label for _, label in model_configs],
        "filtros": {
            "modelo": modelo_filter,
            "tipo_acao": tipo_filter,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "usuario": usuario_filter,
        },
    }
    return render(request, "fluxo/auditoria.html", context)


__all__ = [
    "_build_history_record",
    "_get_unified_history",
    "api_documentos_processo",
    "api_processo_detalhes",
    "auditoria_view",
]
