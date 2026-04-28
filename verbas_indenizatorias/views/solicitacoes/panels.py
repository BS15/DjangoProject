from django.contrib.auth.decorators import permission_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from pagamentos.views.helpers import _resolver_parametros_ordenacao
from verbas_indenizatorias.constants import STATUS_VERBA_APROVADA
from ..shared.registry import _VERBA_CONFIG
from .helpers import resumo_solicitacao


@require_GET
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def painel_revisar_solicitacoes_view(request):
    solicitacoes = []
    for tipo_verba in ("diaria", "reembolso", "jeton", "auxilio"):
        config = _VERBA_CONFIG[tipo_verba]
        itens = (
            config["model"]
            .objects.select_related("beneficiario", "status")
            .filter(
                processo__isnull=True,
                status__status_choice__iexact=STATUS_VERBA_APROVADA,
            )
            .order_by("-id")
        )
        solicitacoes.extend(resumo_solicitacao(tipo_verba, item) for item in itens)

    ordem, direcao, _ = _resolver_parametros_ordenacao(
        request,
        campos_permitidos={
            "tipo": "tipo",
            "id": "id",
            "beneficiario": "beneficiario",
            "referencia": "referencia",
            "valor_total": "valor_total",
            "status": "status",
        },
        default_ordem="id",
        default_direcao="desc",
    )

    def _sort_key(item):
        status_value = getattr(item.get("status"), "status_choice", "") if item.get("status") else ""
        map_keys = {
            "tipo": (item.get("tipo_label") or "").lower(),
            "id": item.get("id") or 0,
            "beneficiario": (item.get("beneficiario_nome") or "").lower(),
            "referencia": (item.get("referencia") or "").lower(),
            "valor_total": item.get("valor_total") or 0,
            "status": status_value.lower(),
        }
        return map_keys.get(ordem, item.get("id") or 0)

    solicitacoes = sorted(solicitacoes, key=_sort_key, reverse=(direcao == "desc"))

    return render(
        request,
        "verbas/revisar_solicitacoes_verba.html",
        {
            "solicitacoes": solicitacoes,
            "ordem": ordem,
            "direcao": direcao,
        },
    )


@require_GET
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def revisar_solicitacao_verba_view(request, tipo_verba, pk):
    config = _VERBA_CONFIG.get(tipo_verba)
    if not config:
        raise Http404("Tipo de solicitação inválido para revisão.")

    solicitacao = get_object_or_404(
        config["model"].objects.select_related("beneficiario", "status"),
        id=pk,
    )
    documentos = solicitacao.documentos.select_related("tipo").all()
    status_atual = (solicitacao.status.status_choice if solicitacao.status else "").upper()
    pode_revisar = (status_atual == STATUS_VERBA_APROVADA) and not solicitacao.processo_id

    context = {
        "solicitacao": resumo_solicitacao(tipo_verba, solicitacao),
        "obj": solicitacao,
        "documentos": documentos,
        "tipo_documento_seguro": config["doc_tipo_seguro"],
        "pode_revisar": pode_revisar,
    }
    return render(request, "verbas/revisar_solicitacao_verba.html", context)
