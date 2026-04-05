import logging

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..models.fluxo import AssinaturaAutentique
from ..services import construir_signatarios_padrao, disparar_assinatura_rascunho

logger = logging.getLogger(__name__)


def painel_assinaturas_view(request):
    """Exibe painel de assinaturas do usuário atual.

    Inclui:
    - meus_documentos: assinaturas criadas pelo usuário.
    - para_assinar: assinaturas pendentes com link pessoal do usuário.
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
                assinatura.meu_link = signer_data.get('short_link', '') or assinatura.autentique_url
                para_assinar.append(assinatura)

    return render(request, 'fluxo/painel_assinaturas.html', {
        'meus_documentos': meus_documentos,
        'para_assinar': para_assinar,
    })


@require_POST
def disparar_assinatura_view(request, assinatura_id):
    """Dispara um rascunho de assinatura para a Autentique via POST.

    Apenas o criador do rascunho pode realizar o envio.
    """
    assinatura = get_object_or_404(AssinaturaAutentique, id=assinatura_id, status='RASCUNHO')

    if assinatura.criador != request.user:
        raise PermissionDenied("Apenas o criador do documento pode disparar esta assinatura.")

    entidade = assinatura.entidade_relacionada

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

