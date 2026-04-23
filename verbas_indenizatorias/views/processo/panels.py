from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from pagamentos.domain_models import Processo
from pagamentos.forms import DocumentoFormSet, DocumentoOrcamentarioFormSet, PendenciaFormSet, ProcessoForm
from verbas_indenizatorias.constants import STATUS_VERBA_APROVADA
from .helpers import _montar_contexto_processo_verbas, _pode_gerenciar_processo_verbas_da_entidade
from ..shared.registry import _VERBA_CONFIG


_SOLICITACAO_LABELS = {
    "diaria": "Diária",
    "reembolso": "Reembolso",
    "jeton": "Jeton",
    "auxilio": "Auxílio",
}
def _resumo_solicitacao(tipo_verba, solicitacao):
    """Normaliza dados de exibição da solicitação para fila e tela de revisão."""
    if tipo_verba == "diaria":
        data_saida = solicitacao.data_saida.strftime("%d/%m/%Y") if solicitacao.data_saida else "-"
        data_retorno = solicitacao.data_retorno.strftime("%d/%m/%Y") if solicitacao.data_retorno else "-"
        referencia = f"{solicitacao.numero_siscac or solicitacao.id} — {data_saida} a {data_retorno}"
    elif tipo_verba == "jeton":
        referencia = f"{solicitacao.numero_sequencial} — Reunião {solicitacao.reuniao}"
    elif tipo_verba == "auxilio":
        referencia = f"{solicitacao.numero_sequencial} — {solicitacao.objetivo or 'Representação'}"
    else:
        referencia = f"{solicitacao.numero_sequencial} — {solicitacao.cidade_origem} → {solicitacao.cidade_destino}"

    return {
        "id": solicitacao.id,
        "tipo_verba": tipo_verba,
        "tipo_label": _SOLICITACAO_LABELS[tipo_verba],
        "beneficiario_nome": getattr(solicitacao.beneficiario, "nome", "-"),
        "status": solicitacao.status,
        "referencia": referencia,
        "valor_total": solicitacao.valor_total,
    }


@require_GET
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def verbas_panel_view(request):
    return render(request, "verbas/verbas_panel.html")


@require_GET
def editar_processo_verbas_view(request, pk):
    """Hub de edição para processos de verbas indenizatórias."""
    processo = get_object_or_404(Processo, id=pk)
    if not _pode_gerenciar_processo_verbas_da_entidade(request.user, processo):
        raise PermissionDenied("Acesso negado para edição deste processo de verbas.")
    context = _montar_contexto_processo_verbas(processo)
    return render(request, "verbas/editar_processo_verbas_hub.html", context)


@require_GET
def editar_processo_verbas_capa_view(request, pk):
    """Spoke de edição da capa do processo de verbas."""
    processo = get_object_or_404(Processo, id=pk)
    if not _pode_gerenciar_processo_verbas_da_entidade(request.user, processo):
        raise PermissionDenied("Acesso negado para edição deste processo de verbas.")
    processo_form = ProcessoForm(instance=processo, prefix="processo")
    context = _montar_contexto_processo_verbas(processo, processo_form=processo_form)
    return render(request, "verbas/editar_processo_verbas_capa.html", context)


@require_GET
def editar_processo_verbas_pendencias_view(request, pk):
    """Spoke de edição das pendências do processo de verbas."""
    processo = get_object_or_404(Processo, id=pk)
    if not _pode_gerenciar_processo_verbas_da_entidade(request.user, processo):
        raise PermissionDenied("Acesso negado para edição deste processo de verbas.")
    pendencia_formset = PendenciaFormSet(instance=processo, prefix="pendencia")
    context = _montar_contexto_processo_verbas(processo, pendencia_formset=pendencia_formset)
    return render(request, "verbas/editar_processo_verbas_pendencias.html", context)


@require_GET
def editar_processo_verbas_itens_view(request, pk):
    """Spoke de gestão dos itens individuais vinculados ao processo."""
    processo = get_object_or_404(Processo, id=pk)
    if not _pode_gerenciar_processo_verbas_da_entidade(request.user, processo):
        raise PermissionDenied("Acesso negado para edição deste processo de verbas.")
    context = _montar_contexto_processo_verbas(processo)
    return render(request, "verbas/editar_processo_verbas_itens.html", context)


@require_GET
def editar_processo_verbas_documentos_view(request, pk):
    """Spoke de gestão de documentos do processo e cards read-only dos docs de verba."""
    processo = get_object_or_404(Processo, id=pk)
    if not _pode_gerenciar_processo_verbas_da_entidade(request.user, processo):
        raise PermissionDenied("Acesso negado para edição deste processo de verbas.")
    context = _montar_contexto_processo_verbas(processo)
    context.update({
        "documento_formset": DocumentoFormSet(
            instance=processo,
            prefix="documento",
            form_kwargs={"tipo_queryset": context.get("tipos_documento")},
        ),
    })
    return render(request, "verbas/editar_processo_verbas_documentos.html", context)


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
        solicitacoes.extend(_resumo_solicitacao(tipo_verba, item) for item in itens)

    solicitacoes.sort(key=lambda item: item["id"], reverse=True)
    return render(request, "verbas/revisar_solicitacoes_verba.html", {"solicitacoes": solicitacoes})


@require_GET
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def revisar_solicitacao_verba_view(request, tipo_verba, pk):
    config = _VERBA_CONFIG.get(tipo_verba)
    if not config:
        from django.http import Http404
        raise Http404("Tipo de solicitação inválido para revisão.")

    solicitacao = get_object_or_404(
        config["model"].objects.select_related("beneficiario", "status"),
        id=pk,
    )
    documentos = solicitacao.documentos.select_related("tipo").all()
    status_atual = (solicitacao.status.status_choice if solicitacao.status else "").upper()
    pode_revisar = (status_atual == STATUS_VERBA_APROVADA) and not solicitacao.processo_id

    context = {
        "solicitacao": _resumo_solicitacao(tipo_verba, solicitacao),
        "obj": solicitacao,
        "documentos": documentos,
        "tipo_documento_seguro": config["doc_tipo_seguro"],
        "pode_revisar": pode_revisar,
    }
    return render(request, "verbas/revisar_solicitacao_verba.html", context)
