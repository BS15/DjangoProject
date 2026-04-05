import logging

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from ..models.fluxo import AssinaturaAutentique
from ..services import construir_signatarios_padrao, disparar_assinatura_rascunho

logger = logging.getLogger(__name__)


def painel_assinaturas_view(request):
    """
    Dashboard showing:
    - meus_documentos: signatures created by the current user
    - para_assinar: PENDENTE signatures where the user's email is a key in dados_signatarios,
      enriched with that user's specific signing link from dados_signatarios.
    """
    meus_documentos = AssinaturaAutentique.objects.filter(
        criador=request.user
    ).select_related('content_type').order_by('-id')

    pendentes = AssinaturaAutentique.objects.filter(
        status='PENDENTE'
    ).select_related('content_type')

    user_email = request.user.email
    para_assinar = []
    if user_email:
        for assinatura in pendentes:
            signer_data = (assinatura.dados_signatarios or {}).get(user_email)
            if signer_data:
                # Attach user's personal link so the template can use it directly
                assinatura.meu_link = signer_data.get('short_link', '') or assinatura.autentique_url
                para_assinar.append(assinatura)

    return render(request, 'fluxo/painel_assinaturas.html', {
        'meus_documentos': meus_documentos,
        'para_assinar': para_assinar,
    })


def disparar_assinatura_view(request, assinatura_id):
    """
    POST-only view. Dispatches a RASCUNHO AssinaturaAutentique to Autentique.

    Reads the draft PDF from assinatura.arquivo, reconstructs the signatarios
    list from the related entity, then calls enviar_documento_para_assinatura
    passing the AssinaturaAutentique instance directly so the service updates
    it in-place (sets autentique_id, dados_signatarios, status='PENDENTE').
    """
    if request.method != 'POST':
        return redirect('painel_assinaturas')

    assinatura = get_object_or_404(AssinaturaAutentique, id=assinatura_id, status='RASCUNHO')

    # Only the creator or backoffice can dispatch
    is_backoffice = request.user.has_perm('processos.acesso_backoffice')
    is_criador = assinatura.criador == request.user
    if not (is_backoffice or is_criador):
        raise PermissionDenied("Você não tem permissão para disparar esta assinatura.")

    entidade = assinatura.entidade_relacionada

    # Build the signatarios list from the related entity
    signatarios = construir_signatarios_padrao(entidade)
    if not signatarios:
        messages.error(request, "Não foi possível determinar os signatários para este documento.")
        return redirect('painel_assinaturas')

    nome_doc = f"{assinatura.tipo_documento}_{assinatura_id}"

    try:
        disparar_assinatura_rascunho(assinatura, signatarios, nome_doc=nome_doc)
        messages.success(request, "Documento enviado para assinatura com sucesso!")
    except Exception as exc:
        logger.exception("Erro ao disparar assinatura %s para Autentique", assinatura_id)
        assinatura.status = 'ERRO'
        assinatura.save(update_fields=['status'])
        messages.error(request, f"Erro ao enviar para Autentique: {exc}")

    return redirect('painel_assinaturas')

