"""Views e APIs de auditoria/historico."""

from urllib.parse import urlencode

from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
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
from .helpers import (
    _aplicar_filtros_historico,
    _build_history_record,
    _build_payload_documentos_processo_auditoria,
    _build_payload_processo_detalhes,
    _get_unified_history,
    _normalizar_filtro_opcao,
)


@permission_required("processos.pode_auditar_conselho", raise_exception=True)
@require_GET
@xframe_options_sameorigin
def api_documentos_processo(request, processo_id):
    """Retorna documentos e metadados correlatos de um processo para visualização de auditoria."""
    processo = get_object_or_404(Processo, id=processo_id)
    return JsonResponse(_build_payload_documentos_processo_auditoria(processo))


@permission_required("processos.pode_auditar_conselho", raise_exception=True)
@require_GET
def api_processo_detalhes(request):
    """Retorna detalhes de um processo por ``id`` informado via query string."""
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

    return JsonResponse(_build_payload_processo_detalhes(processo))


@permission_required("processos.pode_auditar_conselho", raise_exception=True)
def auditoria_view(request):
    """Renderiza a trilha de auditoria consolidada de modelos financeiros."""
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

    modelos_disponiveis = [label for _, label in model_configs]
    modelo_filter = _normalizar_filtro_opcao(
        request.GET.get("modelo", "").strip(),
        {*modelos_disponiveis, ""},
        default="",
    )
    tipo_filter = _normalizar_filtro_opcao(
        request.GET.get("tipo_acao", "").strip(),
        {"", "+", "~", "-"},
        default="",
    )
    data_inicio = request.GET.get("data_inicio", "").strip()
    data_fim = request.GET.get("data_fim", "").strip()
    usuario_filter = request.GET.get("usuario", "").strip()
    ordem = _normalizar_filtro_opcao(
        request.GET.get("ordem", "data"),
        {"data", "modelo", "id", "acao", "usuario", "descricao"},
        default="data",
    )
    direcao = _normalizar_filtro_opcao(
        request.GET.get("direcao", "desc"),
        {"asc", "desc"},
        default="desc",
    )

    campos_ordenacao = {
        "data": "history_date",
        "modelo": "modelo",
        "id": "object_id",
        "acao": "history_type",
        "usuario": "history_user",
        "descricao": "str_repr",
    }
    sort_key = campos_ordenacao[ordem]
    reverse_sort = direcao == "desc"

    all_records = []
    for history_model, label in model_configs:
        if modelo_filter and modelo_filter != label:
            continue
        qs = history_model.objects.select_related("history_user").all()
        qs = _aplicar_filtros_historico(
            qs,
            tipo_acao=tipo_filter,
            data_inicio=data_inicio,
            data_fim=data_fim,
            usuario=usuario_filter,
        )
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

    def _record_sort_key(record):
        if sort_key == "history_user":
            user = record.get("history_user")
            if not user:
                return ""
            return (user.get_full_name() or user.username or "").lower()

        value = record.get(sort_key)
        if value is None:
            return ""
        if isinstance(value, str):
            return value.lower()
        return value

    all_records.sort(key=_record_sort_key, reverse=reverse_sort)
    total = len(all_records)
    all_records = all_records[:500]

    sort_base_qs = urlencode(
        {
            "modelo": modelo_filter,
            "tipo_acao": tipo_filter,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "usuario": usuario_filter,
        }
    )
    sort_base_qs = f"{sort_base_qs}&" if sort_base_qs else ""

    context = {
        "registros": all_records,
        "total": total,
        "modelos_disponiveis": modelos_disponiveis,
        "ordem": ordem,
        "direcao": direcao,
        "sort_base_qs": sort_base_qs,
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
