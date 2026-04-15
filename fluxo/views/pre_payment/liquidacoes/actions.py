"""Ação POST de alternância de ateste de liquidação."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from fiscal.models import DocumentoFiscal
from fluxo.domain_models import Processo


logger = logging.getLogger(__name__)


@permission_required("fluxo.pode_atestar_liquidacao", raise_exception=True)
@require_POST
def alternar_ateste_nota(request, pk):
    """Permite atestar ou remover o ateste de uma nota diretamente pelo painel."""
    if not request.user.has_perm("fluxo.pode_atestar_liquidacao"):
        raise PermissionDenied
    nota = get_object_or_404(DocumentoFiscal, id=pk)

    nota.atestada = not nota.atestada
    nota.save()

    if nota.atestada:
        messages.success(request, f"Nota Fiscal #{nota.numero_nota_fiscal} ATESTADA com sucesso!")
    else:
        messages.warning(request, f"Ateste da Nota Fiscal #{nota.numero_nota_fiscal} foi revogado.")

    return redirect("painel_liquidacoes")


@permission_required("fluxo.pode_operar_contas_pagar", raise_exception=True)
@require_POST
def avancar_para_pagamento_view(request, pk):
    """Avanca processo de AGUARDANDO LIQUIDACAO para A PAGAR - PENDENTE AUTORIZACAO."""
    processo = get_object_or_404(Processo, id=pk)
    status_atual = processo.status.status_choice.upper() if processo.status else ""

    if not status_atual.startswith("AGUARDANDO LIQUIDAÇÃO"):
        messages.error(
            request,
            f'O processo #{pk} não está em status "Aguardando Liquidação" '
            f'(status atual: "{processo.status}"). Ação não permitida.',
        )
        return redirect("editar_processo", pk=pk)

    try:
        with transaction.atomic():
            processo.avancar_status("A PAGAR - PENDENTE AUTORIZAÇÃO", usuario=request.user)

        messages.success(request, f'Processo #{pk} avançado com sucesso para "A Pagar - Pendente Autorização".')
    except ValidationError as ve:
        for erro in ve.messages:
            messages.error(request, erro)
    except (DatabaseError, TypeError, ValueError):
        logger.exception("Erro ao avançar processo %s para pagamento", pk)
        messages.error(request, "Erro interno ao avançar o processo. Tente novamente.")

    return redirect("editar_processo", pk=pk)


__all__ = ["alternar_ateste_nota", "avancar_para_pagamento_view"]
