import logging

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect

from fluxo.models import AssinaturaAutentique
from fluxo.services.shared import (
    AssinaturaSignatariosError,
    construir_signatarios_padrao,
    enviar_para_assinatura,
    sincronizar_assinatura,
)
from fluxo.views.signature_access import user_is_entity_owner
from verbas_indenizatorias.models import Diaria


logger = logging.getLogger(__name__)


def sincronizar_assinatura_view(request, assinatura_id):
    assinatura = get_object_or_404(AssinaturaAutentique, id=assinatura_id)

    is_backoffice = request.user.has_perm('fluxo.pode_gerenciar_diarias')
    entidade = assinatura.entidade_relacionada
    is_owner = user_is_entity_owner(request.user, entidade)
    if not (is_backoffice or is_owner):
        raise PermissionDenied('Voce nao tem permissao para sincronizar este documento.')

    if assinatura.status == 'ASSINADO':
        messages.info(request, 'Este documento ja foi assinado.')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    try:
        status_sync = sincronizar_assinatura(assinatura)
        if status_sync == 'signed':
            messages.success(request, 'Documento assinado e sincronizado com sucesso!')
        else:
            messages.info(request, 'O documento ainda esta pendente de assinatura no Autentique.')
    except (AssinaturaSignatariosError, OSError, RuntimeError, TypeError, ValueError):
        logger.exception("Erro ao sincronizar assinatura %s", assinatura_id)
        messages.error(request, 'Erro ao verificar assinatura. Tente novamente.')
    return redirect(request.META.get('HTTP_REFERER', '/'))


def reenviar_assinatura_view(request, diaria_id):
    diaria = get_object_or_404(Diaria, id=diaria_id)

    is_backoffice = request.user.has_perm('fluxo.pode_gerenciar_diarias')
    is_owner = user_is_entity_owner(request.user, diaria)
    if not (is_backoffice or is_owner):
        raise PermissionDenied('Voce nao tem permissao para reenviar este documento.')

    try:
        signatarios = construir_signatarios_padrao(diaria)
        if not signatarios:
            messages.error(request, 'Nao foi possivel determinar os signatarios para esta diaria.')
            return redirect('gerenciar_diaria', pk=diaria.id)

        enviar_para_assinatura(
            entidade=diaria,
            tipo_documento='SCD',
            nome_doc=f'SCD_{diaria.numero_siscac}',
            signatarios=signatarios,
            doc_type='scd',
        )
        messages.success(request, 'SCD reenviado para assinatura com sucesso!')
    except (AssinaturaSignatariosError, OSError, RuntimeError, TypeError, ValueError):
        logger.exception("Erro ao reenviar SCD da diária %s para assinatura", diaria_id)
        messages.error(request, 'Erro ao reenviar SCD para assinatura. Tente novamente.')

    return redirect('gerenciar_diaria', pk=diaria.id)
