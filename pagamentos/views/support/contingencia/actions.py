"""Acoes de contingencia (POST views)."""

import json
import logging

logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from pagamentos.domain_models import Contingencia, Processo
from pagamentos.views.helpers import (
    determinar_requisitos_contingencia,
    normalizar_dados_propostos_contingencia,
    sincronizar_flag_contingencia_processo,
    processar_aprovacao_contingencia,
    processar_revisao_contadora_contingencia,
)
from .helpers import _validar_permissao_por_etapa


@require_POST
@permission_required("pagamentos.acesso_backoffice", raise_exception=True)
def add_contingencia_action(request: HttpRequest) -> HttpResponse:
    """Cria uma contingencia (correcao manual) para um processo."""
    processo_id = (request.POST.get("processo_id", "") or "").strip()
    justificativa = (request.POST.get("justificativa", "") or "").strip()
    dados_propostos_raw = (request.POST.get("dados_propostos", "{}") or "{}").strip()

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
@permission_required("pagamentos.acesso_backoffice", raise_exception=True)
def analisar_contingencia_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Aprova ou rejeita uma contingencia pendente."""
    acao = (request.POST.get("action", "")).strip()
    parecer = (request.POST.get("parecer", "")).strip()

    contingencia = get_object_or_404(Contingencia, pk=pk)

    if contingencia.status in {"APROVADA", "REJEITADA"}:
        messages.error(request, "Esta contingência já foi finalizada e não pode ser alterada.")
        return redirect("painel_contingencias")

    if acao == "aprovar":
        sucesso, msg_erro = processar_aprovacao_contingencia(contingencia, request.user, parecer)
        if not sucesso:
            messages.error(request, msg_erro)
        else:
            novo_status = contingencia.status
            if novo_status == "PENDENTE_CONTADOR":
                messages.success(request, f"Contingência #{contingencia.pk} aprovada e enviada para revisão da Contadora.")
            elif novo_status == "APROVADA":
                messages.success(request, f"Contingência #{contingencia.pk} aprovada e aplicada ao processo.")
            else:
                messages.success(request, f"Contingência #{contingencia.pk} aprovada. Próxima etapa: {novo_status}.")
            logger.info(
                "mutation=aprovar_contingencia contingencia_id=%s user_id=%s novo_status=%s",
                contingencia.pk, request.user.pk, novo_status,
            )
    elif acao == "rejeitar":
        with transaction.atomic():
            contingencia.status = "REJEITADA"
            contingencia._history_user = request.user
            contingencia.save(update_fields=["status"])
            sincronizar_flag_contingencia_processo(contingencia.processo)
        messages.success(request, f"Contingência #{contingencia.pk} rejeitada.")
        logger.info(
            "mutation=rejeitar_contingencia contingencia_id=%s user_id=%s",
            contingencia.pk, request.user.pk,
        )
    elif acao == "revisar_contadora":
        if contingencia.status != "PENDENTE_CONTADOR":
            messages.error(request, "A revisão contábil só pode ser feita quando a contingência estiver pendente da contadora.")
            return redirect("painel_contingencias")
        sucesso, msg_erro = processar_revisao_contadora_contingencia(contingencia, request.user, parecer)
        if not sucesso:
            messages.error(request, msg_erro)
        else:
            messages.success(request, f"Contingência #{contingencia.pk} revisada pela contadora e aplicada ao processo.")
            logger.info(
                "mutation=revisar_contingencia_contadora contingencia_id=%s user_id=%s",
                contingencia.pk, request.user.pk,
            )
    else:
        messages.error(request, "Ação inválida.")

    return redirect("painel_contingencias")


__all__ = [
    "add_contingencia_action",
    "analisar_contingencia_action",
]
