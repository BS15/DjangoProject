"""Views de suporte transversal: pendencias, contingencias e devolucoes."""

import json
from decimal import Decimal
from typing import Any, cast

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from ...filters import ContingenciaFilter, DevolucaoFilter, PendenciaFilter, ProcessoFilter
from ...forms import DevolucaoForm
from ...models import Contingencia, Devolucao, Pendencia, Processo
from ..shared import apply_filterset, render_filtered_list
from .helpers import _obter_campo_ordenacao, aplicar_aprovacao_contingencia


def home_page(request: HttpRequest) -> HttpResponse:
    """Lista processos no painel inicial com filtro e ordenacao segura."""
    order_field = _obter_campo_ordenacao(
        request,
        campos_permitidos={
            "id": "id",
            "credor": "credor__nome",
            "data_empenho": "data_empenho",
            "status": "status__status_choice",
            "tipo_pagamento": "tipo_pagamento__tipo_de_pagamento",
            "valor_liquido": "valor_liquido",
        },
    )

    processos_base = Processo.objects.all().order_by(order_field)
    meu_filtro = apply_filterset(request, ProcessoFilter, processos_base)

    context: dict[str, Any] = {
        "lista_processos": meu_filtro.qs,
        "meu_filtro": meu_filtro,
        "ordem": request.GET.get("ordem", "id"),
        "direcao": request.GET.get("direcao", "desc"),
    }
    return render(request, "home.html", context)


@require_GET
@permission_required("processos.acesso_backoffice", raise_exception=True)
def painel_pendencias_view(request: HttpRequest) -> HttpResponse:
    queryset_base = Pendencia.objects.select_related(
        "processo", "status", "tipo", "processo__credor", "processo__status"
    ).all().order_by("-id")
    return render_filtered_list(
        request,
        queryset=queryset_base,
        filter_class=PendenciaFilter,
        template_name="fluxo/painel_pendencias.html",
        items_key="pendencias",
    )


@require_GET
@permission_required("processos.acesso_backoffice", raise_exception=True)
def painel_contingencias_view(request: HttpRequest) -> HttpResponse:
    queryset = Contingencia.objects.select_related("processo", "solicitante").order_by("-data_solicitacao")
    return render_filtered_list(
        request,
        queryset=queryset,
        filter_class=ContingenciaFilter,
        template_name="fluxo/painel_contingencias.html",
        items_key="contingencias",
        filter_key="filter",
    )


@require_GET
@permission_required("processos.acesso_backoffice", raise_exception=True)
def add_contingencia_view(request: HttpRequest) -> HttpResponse:
    """Renderiza o formulário para abertura de contingência."""
    return render(request, "fluxo/add_contingencia.html")


@require_POST
@permission_required("processos.acesso_backoffice", raise_exception=True)
def add_contingencia_action(request: HttpRequest) -> HttpResponse:
    """Cria uma contingência (correção manual) para um processo."""
    processo_id = cast(str, request.POST.get("processo_id", "")).strip()
    justificativa = cast(str, request.POST.get("justificativa", "")).strip()
    dados_propostos_raw = cast(str, request.POST.get("dados_propostos", "{}")).strip()

    if not processo_id or not justificativa:
        messages.error(request, "Processo e justificativa são obrigatórios.")
        return redirect("add_contingencia")

    if not processo_id.isdigit():
        messages.error(request, "ID do Processo inválido.")
        return redirect("add_contingencia")

    processo = get_object_or_404(Processo, pk=int(processo_id))

    try:
        dados_propostos_raw_obj = json.loads(dados_propostos_raw) if dados_propostos_raw else {}
        dados_propostos = dados_propostos_raw_obj if isinstance(dados_propostos_raw_obj, dict) else {}
    except (json.JSONDecodeError, ValueError):
        dados_propostos = {}

    with transaction.atomic():
        contingencia = Contingencia.objects.create(
            processo=processo,
            solicitante=request.user,
            justificativa=justificativa,
            dados_propostos=dados_propostos,
            status="PENDENTE_SUPERVISOR",
        )
        processo.em_contingencia = True
        processo.save(update_fields=["em_contingencia"])

    messages.success(
        request,
        f"Contingência #{contingencia.pk} aberta com sucesso para o Processo #{processo.pk}. "
        "Aguardando aprovação do Supervisor.",
    )
    return redirect("home_page")


@require_POST
@permission_required("processos.acesso_backoffice", raise_exception=True)
def analisar_contingencia_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Aprova ou rejeita uma contingência pendente."""
    contingencia = get_object_or_404(Contingencia, pk=pk)
    action = cast(str, request.POST.get("action", "")).strip()

    if action == "aprovar":
        sucesso, msg_erro = aplicar_aprovacao_contingencia(contingencia)
        if sucesso:
            messages.success(
                request,
                f"Contingência #{contingencia.pk} aprovada com sucesso. O Processo #{contingencia.processo.pk} foi atualizado.",
            )
        else:
            messages.error(request, msg_erro)
    elif action == "rejeitar":
        with transaction.atomic():
            contingencia.status = "REJEITADA"
            contingencia.save(update_fields=["status"])

            processo = contingencia.processo
            processo.em_contingencia = False
            processo.save(update_fields=["em_contingencia"])

        messages.warning(request, f"Contingência #{contingencia.pk} rejeitada.")
    else:
        messages.error(request, "Ação inválida.")

    return redirect("painel_contingencias")


@require_GET
@permission_required("processos.acesso_backoffice", raise_exception=True)
def painel_devolucoes_view(request: HttpRequest) -> HttpResponse:
    queryset = Devolucao.objects.select_related("processo", "processo__credor").order_by("-data_devolucao")
    meu_filtro = apply_filterset(request, DevolucaoFilter, queryset)
    total_valor = meu_filtro.qs.aggregate(total=Sum("valor_devolvido"))["total"] or Decimal("0")
    return render(
        request,
        "fluxo/devolucoes_list.html",
        {
            "filter": meu_filtro,
            "devolucoes": meu_filtro.qs,
            "total_valor": total_valor,
        },
    )


@require_GET
@permission_required("processos.acesso_backoffice", raise_exception=True)
def registrar_devolucao_view(request: HttpRequest, processo_id: int) -> HttpResponse:
    """Renderiza formulário para registrar devolução vinculada ao processo."""
    processo = get_object_or_404(Processo, id=processo_id)
    form = DevolucaoForm()

    return render(request, "fluxo/add_devolucao.html", {"form": form, "processo": processo})


@require_POST
@permission_required("processos.acesso_backoffice", raise_exception=True)
def registrar_devolucao_action(request: HttpRequest, processo_id: int) -> HttpResponse:
    """Persiste devolução vinculada ao processo a partir do POST do formulário."""
    processo = get_object_or_404(Processo, id=processo_id)
    form = DevolucaoForm(request.POST, request.FILES)

    if form.is_valid():
        devolucao = form.save(commit=False)
        devolucao.processo = processo
        devolucao.save()
        messages.success(request, "Devolução registrada com sucesso.")
        return redirect("process_detail", processo.id)

    return render(request, "fluxo/add_devolucao.html", {"form": form, "processo": processo})


@require_GET
@permission_required("processos.acesso_backoffice", raise_exception=True)
def process_detail_view(request: HttpRequest, pk: int) -> HttpResponse:
    processo: Any = get_object_or_404(Processo, pk=pk)
    documentos = processo.documentos.all()
    status_permite_devolucao = {
        "PAGO - A CONTABILIZAR",
        "CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL",
        "APROVADO - PENDENTE ARQUIVAMENTO",
        "ARQUIVADO",
    }
    pode_registrar_devolucao = processo.status and processo.status.status_choice in status_permite_devolucao
    return render(
        request,
        "fluxo/process_detail.html",
        {
            "processo": processo,
            "documentos": documentos,
            "pode_registrar_devolucao": pode_registrar_devolucao,
        },
    )


__all__ = [
    "home_page",
    "painel_pendencias_view",
    "painel_contingencias_view",
    "add_contingencia_view",
    "add_contingencia_action",
    "analisar_contingencia_view",
    "painel_devolucoes_view",
    "registrar_devolucao_view",
    "registrar_devolucao_action",
    "process_detail_view",
]
