"""Ação POST de alternância de ateste de liquidação."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from fiscal.models import DocumentoFiscal
from pagamentos.domain_models import Processo, ProcessoStatus


logger = logging.getLogger(__name__)


@require_POST
@permission_required("pagamentos.pode_atestar_liquidacao", raise_exception=True)
def alternar_ateste_nota_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Permite definir explicitamente o estado de ateste de uma nota pelo painel."""
    estado_bruto = (request.POST.get("estado_alvo") or "").strip().lower()
    if estado_bruto not in {"true", "false", "1", "0", "on", "off"}:
        messages.error(request, "Estado alvo de ateste inválido.")
        return redirect("painel_liquidacoes")

    estado_alvo = estado_bruto in {"true", "1", "on"}

    with transaction.atomic():
        nota = get_object_or_404(DocumentoFiscal.objects.select_for_update(), id=pk)
        if nota.atestada != estado_alvo:
            nota.atestada = estado_alvo
            nota.save(update_fields=["atestada"])
            logger.info("mutation=alternar_ateste_nota nota_id=%s user_id=%s atestada=%s", nota.pk, request.user.pk, nota.atestada)

    if nota.atestada == estado_alvo:
        if estado_alvo:
            messages.success(request, f"Nota Fiscal #{nota.numero_nota_fiscal} ATESTADA com sucesso!")
        else:
            messages.warning(request, f"Ateste da Nota Fiscal #{nota.numero_nota_fiscal} foi revogado.")

    return redirect("painel_liquidacoes")


@require_POST
@permission_required("pagamentos.operador_contas_a_pagar", raise_exception=True)
def avancar_para_pagamento_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Avanca processo de AGUARDANDO LIQUIDACAO para A PAGAR - PENDENTE AUTORIZACAO."""
    try:
        with transaction.atomic():
            processo = Processo.objects.select_for_update().select_related("status").get(id=pk)
            status_atual = processo.status.opcao_status.upper() if processo.status else ""

            if status_atual != ProcessoStatus.AGUARDANDO_LIQUIDACAO:
                messages.error(
                    request,
                    f'O processo #{pk} não está em status "Aguardando Liquidação" '
                    f'(status atual: "{processo.status}"). Ação não permitida.',
                )
                return redirect("editar_processo", pk=pk)

            processo.avancar_status(ProcessoStatus.A_PAGAR_PENDENTE_AUTORIZACAO, usuario=request.user)
            logger.info("mutation=avancar_para_pagamento processo_id=%s user_id=%s novo_status=%s", processo.pk, request.user.pk, ProcessoStatus.A_PAGAR_PENDENTE_AUTORIZACAO)

        messages.success(request, f'Processo #{pk} avançado com sucesso para "A Pagar - Pendente Autorização".')
    except ValidationError as ve:
        for erro in ve.messages:
            messages.error(request, erro)
    except (DatabaseError, TypeError, ValueError):
        logger.exception("Erro ao avançar processo %s para pagamento", pk)
        messages.error(request, "Erro interno ao avançar o processo. Tente novamente.")

    return redirect("editar_processo", pk=pk)


__all__ = ["alternar_ateste_nota_action", "avancar_para_pagamento_action"]
