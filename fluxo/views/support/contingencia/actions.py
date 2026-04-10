"""Acoes de contingencia (POST views)."""

import json
from decimal import Decimal
from typing import cast

import logging
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from fluxo.models import Contingencia, Processo
from fluxo.views.helpers import (
    _obter_campo_ordenacao,
    aplicar_aprovacao_contingencia,
    determinar_requisitos_contingencia,
    normalizar_dados_propostos_contingencia,
    proximo_status_contingencia,
    sincronizar_flag_contingencia_processo,
)
from .helpers import _validar_permissao_por_etapa


@require_POST
@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def add_contingencia_action(request: HttpRequest) -> HttpResponse:
    """Cria uma contingencia (correcao manual) para um processo."""
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
        logger.exception(
            "ValidationError ao normalizar dados de contingência: processo_id=%s",
            processo_id,
        )
        messages.error(request, "Dados propostos inválidos. Verifique o formato e tente novamente.")
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
    """Aprova ou rejeita uma contingencia pendente."""
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
            elif contingencia.status == "PENDENTE_CONTADOR":
                messages.error(request, "Esta contingência deve ser revisada pela contadora para concluir.")
                return redirect("painel_contingencias")
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

        if not request.user.has_perm("fluxo.pode_contabilizar"):
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


__all__ = [
    "add_contingencia_action",
    "analisar_contingencia_view",
]
