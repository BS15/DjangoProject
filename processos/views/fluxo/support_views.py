"""Views de suporte transversal: pendencias, contingencias e devolucoes."""

import json
from decimal import Decimal
from typing import Any, cast

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from ...filters import ContingenciaFilter, DevolucaoFilter, PendenciaFilter, ProcessoFilter
from ...forms import DevolucaoForm
from ...models import Contingencia, Devolucao, Pendencia, Processo
from ..shared import apply_filterset, render_filtered_list
from .helpers import (
    _obter_campo_ordenacao,
    aplicar_aprovacao_contingencia,
    determinar_requisitos_contingencia,
    normalizar_dados_propostos_contingencia,
    proximo_status_contingencia,
    sincronizar_flag_contingencia_processo,
)


def _usuario_pode_acessar_painel_contingencias(user):
    return any(
        user.has_perm(perm)
        for perm in (
            "processos.acesso_backoffice",
            "processos.pode_aprovar_contingencia_supervisor",
            "processos.pode_autorizar_pagamento",
            "processos.pode_auditar_conselho",
            "processos.pode_contabilizar",
        )
    )


def _validar_permissao_por_etapa(user, status_contingencia):
    if status_contingencia == "PENDENTE_SUPERVISOR":
        return user.has_perm("processos.pode_aprovar_contingencia_supervisor")
    if status_contingencia == "PENDENTE_ORDENADOR":
        return user.has_perm("processos.pode_autorizar_pagamento")
    if status_contingencia == "PENDENTE_CONSELHO":
        return user.has_perm("processos.pode_auditar_conselho")
    if status_contingencia == "PENDENTE_CONTADOR":
        return user.has_perm("processos.pode_contabilizar")
    return False


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
def painel_contingencias_view(request: HttpRequest) -> HttpResponse:
    if not _usuario_pode_acessar_painel_contingencias(request.user):
        raise PermissionDenied

    queryset = Contingencia.objects.select_related(
        "processo",
        "solicitante",
        "aprovado_por_supervisor",
        "aprovado_por_ordenador",
        "aprovado_por_conselho",
        "revisado_por_contadora",
    ).order_by("-data_solicitacao")
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

    try:
        dados_propostos = normalizar_dados_propostos_contingencia(dados_propostos)
    except ValidationError as exc:
        messages.error(request, f"Dados propostos inválidos: {exc}")
        return redirect("add_contingencia")

    status_atual_processo = processo.status.status_choice if processo.status else ""
    exige_aprovacao_ordenador, exige_aprovacao_conselho, exige_revisao_contadora = determinar_requisitos_contingencia(status_atual_processo)

    with transaction.atomic():
        contingencia = Contingencia.objects.create(
            processo=processo,
            solicitante=request.user,
            justificativa=justificativa,
            dados_propostos=dados_propostos,
            status="PENDENTE_SUPERVISOR",
            exige_aprovacao_ordenador=exige_aprovacao_ordenador,
            exige_aprovacao_conselho=exige_aprovacao_conselho,
            exige_revisao_contadora=exige_revisao_contadora,
        )
        sincronizar_flag_contingencia_processo(processo)

    cadeia = ["Supervisor/Gerência"]
    if exige_aprovacao_ordenador:
        cadeia.append("Ordenador de Despesa")
    if exige_aprovacao_conselho:
        cadeia.append("Conselho Fiscal")
    if exige_revisao_contadora:
        cadeia.append("Revisão da Contadora")

    messages.success(
        request,
        f"Contingência #{contingencia.pk} aberta com sucesso para o Processo #{processo.pk}. "
        f"Fluxo exigido: {' -> '.join(cadeia)}.",
    )
    return redirect("home_page")


@require_POST
def analisar_contingencia_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Aprova ou rejeita uma contingência pendente."""
    contingencia = get_object_or_404(Contingencia, pk=pk)
    action = cast(str, request.POST.get("action", "")).strip()
    parecer = cast(str, request.POST.get("parecer", "")).strip()

    if contingencia.status in {"APROVADA", "REJEITADA"}:
        messages.warning(request, "Esta contingência já foi finalizada e não pode ser alterada.")
        return redirect("painel_contingencias")

    if action in {"aprovar", "rejeitar"}:
        if not _validar_permissao_por_etapa(request.user, contingencia.status):
            raise PermissionDenied

    if action == "aprovar":
        with transaction.atomic():
            contingencia._history_user = request.user

            if contingencia.status == "PENDENTE_SUPERVISOR":
                proximo_status = proximo_status_contingencia(contingencia)
                contingencia.aprovado_por_supervisor = request.user
                contingencia.parecer_supervisor = parecer or contingencia.parecer_supervisor
                contingencia.data_aprovacao_supervisor = timezone.now()
                if proximo_status == "APROVADA":
                    contingencia.save(
                        update_fields=[
                            "aprovado_por_supervisor",
                            "parecer_supervisor",
                            "data_aprovacao_supervisor",
                        ]
                    )
                    sucesso, msg_erro = aplicar_aprovacao_contingencia(contingencia)
                    if not sucesso:
                        transaction.set_rollback(True)
                        messages.error(request, msg_erro)
                        return redirect("painel_contingencias")
                else:
                    contingencia.status = proximo_status
                    contingencia.save(
                        update_fields=[
                            "aprovado_por_supervisor",
                            "parecer_supervisor",
                            "data_aprovacao_supervisor",
                            "status",
                        ]
                    )
            elif contingencia.status == "PENDENTE_ORDENADOR":
                proximo_status = proximo_status_contingencia(contingencia)
                contingencia.aprovado_por_ordenador = request.user
                contingencia.parecer_ordenador = parecer or contingencia.parecer_ordenador
                contingencia.data_aprovacao_ordenador = timezone.now()
                if proximo_status == "APROVADA":
                    contingencia.save(
                        update_fields=[
                            "aprovado_por_ordenador",
                            "parecer_ordenador",
                            "data_aprovacao_ordenador",
                        ]
                    )
                    sucesso, msg_erro = aplicar_aprovacao_contingencia(contingencia)
                    if not sucesso:
                        transaction.set_rollback(True)
                        messages.error(request, msg_erro)
                        return redirect("painel_contingencias")
                else:
                    contingencia.status = proximo_status
                    contingencia.save(
                        update_fields=[
                            "aprovado_por_ordenador",
                            "parecer_ordenador",
                            "data_aprovacao_ordenador",
                            "status",
                        ]
                    )
            elif contingencia.status == "PENDENTE_CONSELHO":
                proximo_status = proximo_status_contingencia(contingencia)
                contingencia.aprovado_por_conselho = request.user
                contingencia.parecer_conselho = parecer or contingencia.parecer_conselho
                contingencia.data_aprovacao_conselho = timezone.now()
                if proximo_status == "APROVADA":
                    contingencia.save(
                        update_fields=[
                            "aprovado_por_conselho",
                            "parecer_conselho",
                            "data_aprovacao_conselho",
                        ]
                    )
                    sucesso, msg_erro = aplicar_aprovacao_contingencia(contingencia)
                    if not sucesso:
                        transaction.set_rollback(True)
                        messages.error(request, msg_erro)
                        return redirect("painel_contingencias")
                else:
                    contingencia.status = proximo_status
                    contingencia.save(
                        update_fields=[
                            "aprovado_por_conselho",
                            "parecer_conselho",
                            "data_aprovacao_conselho",
                            "status",
                        ]
                    )
            else:
                messages.error(request, "Esta contingência deve ser revisada pela contadora para concluir.")
                return redirect("painel_contingencias")

            sincronizar_flag_contingencia_processo(contingencia.processo)

        if contingencia.status == "PENDENTE_CONTADOR":
            messages.success(
                request,
                f"Etapa aprovada na Contingência #{contingencia.pk}. Aguardando revisão obrigatória da contadora.",
            )
        elif contingencia.status == "APROVADA":
            messages.success(
                request,
                f"Contingência #{contingencia.pk} aprovada e aplicada ao Processo #{contingencia.processo.pk}.",
            )
        else:
            messages.success(request, f"Etapa aprovada na Contingência #{contingencia.pk}.")

    elif action == "rejeitar":
        with transaction.atomic():
            contingencia._history_user = request.user
            contingencia.status = "REJEITADA"
            contingencia.save(update_fields=["status"])

            sincronizar_flag_contingencia_processo(contingencia.processo)

        messages.warning(request, f"Contingência #{contingencia.pk} rejeitada.")

    elif action == "revisar_contadora":
        if contingencia.status != "PENDENTE_CONTADOR":
            messages.error(request, "A revisão contábil só pode ser feita quando a contingência estiver pendente da contadora.")
            return redirect("painel_contingencias")

        if not request.user.has_perm("processos.pode_contabilizar"):
            raise PermissionDenied

        if not parecer:
            messages.error(request, "A revisão da contadora exige um parecer de revisão.")
            return redirect("painel_contingencias")

        with transaction.atomic():
            contingencia._history_user = request.user
            contingencia.parecer_contadora = parecer
            contingencia.revisado_por_contadora = request.user
            contingencia.data_revisao_contadora = timezone.now()
            contingencia.save(
                update_fields=["parecer_contadora", "revisado_por_contadora", "data_revisao_contadora"]
            )

            sucesso, msg_erro = aplicar_aprovacao_contingencia(contingencia)
            if not sucesso:
                transaction.set_rollback(True)
                messages.error(request, msg_erro)
                return redirect("painel_contingencias")

        messages.success(
            request,
            f"Contingência #{contingencia.pk} revisada pela contadora e aplicada ao Processo #{contingencia.processo.pk}.",
        )
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
