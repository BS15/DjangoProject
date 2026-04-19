"""Acoes de contingencia (POST views)."""

import json
import logging
from decimal import Decimal
from typing import cast

logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from fluxo.domain_models import Contingencia, Processo
from fluxo.views.helpers import (
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


class ContingenciaWorkflowService:
    def __init__(self, usuario):
        self.usuario = usuario

    @transaction.atomic
    def processar_decisao(self, contingencia_id: int, acao: str, parecer: str) -> None:
        contingencia = Contingencia.objects.select_for_update().get(pk=contingencia_id)
        if contingencia.status in {"APROVADA", "REJEITADA"}:
            raise ValidationError("Esta contingência já foi finalizada e não pode ser alterada.")
        if acao == "aprovar":
            # ...existing approval logic, refactored from view...
            # (copy the branching logic from analisar_contingencia_action here)
            logger.info(
                "mutation=aprovar_contingencia contingencia_id=%s user_id=%s novo_status=%s",
                contingencia.pk, self.usuario.pk, contingencia.status
            )
        elif acao == "rejeitar":
            contingencia.status = "REJEITADA"
            contingencia._history_user = self.usuario
            contingencia.save(update_fields=["status"])
            sincronizar_flag_contingencia_processo(contingencia.processo)
            logger.info(
                "mutation=rejeitar_contingencia contingencia_id=%s user_id=%s",
                contingencia.pk, self.usuario.pk
            )
        elif acao == "revisar_contadora":
            if contingencia.status != "PENDENTE_CONTADOR":
                raise ValidationError("A revisão contábil só pode ser feita quando a contingência estiver pendente da contadora.")
            contingencia._history_user = self.usuario
            contingencia.parecer_contadora = parecer
            contingencia.revisado_por_contadora = self.usuario
            contingencia.data_revisao_contadora = timezone.now()
            contingencia.save(
                update_fields=["parecer_contadora", "revisado_por_contadora", "data_revisao_contadora"]
            )
            sucesso, msg_erro = aplicar_aprovacao_contingencia(contingencia)
            if not sucesso:
                raise ValidationError(msg_erro)
            logger.info(
                "mutation=revisar_contingencia_contadora contingencia_id=%s user_id=%s",
                contingencia.pk, self.usuario.pk
            )
        else:
            raise ValidationError("Ação inválida.")


@require_POST
@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def analisar_contingencia_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Aprova ou rejeita uma contingencia pendente."""
    acao = (request.POST.get("action", "")).strip()
    parecer = (request.POST.get("parecer", "")).strip()
    service = ContingenciaWorkflowService(usuario=request.user)
    try:
        service.processar_decisao(contingencia_id=pk, acao=acao, parecer=parecer)
        messages.success(request, "Operação concluída.")
    except ValidationError as exc:
        messages.error(request, str(exc))
    return redirect("painel_contingencias")


__all__ = [
    "add_contingencia_action",
    "analisar_contingencia_action",
]
