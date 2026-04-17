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
from fluxo.domain_models import Processo, ProcessoStatus


logger = logging.getLogger(__name__)


@require_POST
@permission_required("fluxo.pode_atestar_liquidacao", raise_exception=True)
def alternar_ateste_nota_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Permite atestar ou remover o ateste de uma nota diretamente pelo painel."""
    nota = get_object_or_404(DocumentoFiscal, id=pk)

    nota.atestada = not nota.atestada
    nota.save()

    if nota.atestada:
        messages.success(request, f"Nota Fiscal #{nota.numero_nota_fiscal} ATESTADA com sucesso!")
    else:
        messages.warning(request, f"Ateste da Nota Fiscal #{nota.numero_nota_fiscal} foi revogado.")

    return redirect("painel_liquidacoes")


@require_POST
@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
def avancar_para_pagamento_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Avanca processo de AGUARDANDO LIQUIDACAO para A PAGAR - PENDENTE AUTORIZACAO."""
    processo = get_object_or_404(Processo, id=pk)
    status_atual = processo.status.status_choice.upper() if processo.status else ""

    if status_atual != ProcessoStatus.AGUARDANDO_LIQUIDACAO:
        messages.error(
            request,
            f'O processo #{pk} não está em status "Aguardando Liquidação" '
            f'(status atual: "{processo.status}"). Ação não permitida.',
        )
        return redirect("editar_processo", pk=pk)

    try:
        with transaction.atomic():
            processo.avancar_status(ProcessoStatus.A_PAGAR_PENDENTE_AUTORIZACAO, usuario=request.user)

        messages.success(request, f'Processo #{pk} avançado com sucesso para "A Pagar - Pendente Autorização".')
    except ValidationError as ve:
        for erro in ve.messages:
            messages.error(request, erro)
    except (DatabaseError, TypeError, ValueError):
        logger.exception("Erro ao avançar processo %s para pagamento", pk)
        messages.error(request, "Erro interno ao avançar o processo. Tente novamente.")

    return redirect("editar_processo", pk=pk)


__all__ = ["alternar_ateste_nota_action", "avancar_para_pagamento_action"]
