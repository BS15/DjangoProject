import logging

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from commons.shared.signature_services import AssinaturaSignatariosError, disparar_assinatura_rascunho_com_signatarios
from pagamentos.models import AssinaturaAutentique

logger = logging.getLogger(__name__)


def painel_assinaturas_view(request):
    """Exibe painel de assinaturas do usuário atual."""
    meus_documentos = AssinaturaAutentique.objects.filter(criador=request.user).select_related("content_type").order_by("-id")

    pendentes = AssinaturaAutentique.objects.filter(status="PENDENTE").select_related("content_type")

    user_email = request.user.email
    para_assinar = []
    if user_email:
        for assinatura in pendentes:
            signer_data = (assinatura.dados_signatarios or {}).get(user_email)
            if signer_data:
                assinatura.meu_link = signer_data.get("short_link", "") or assinatura.autentique_url
                para_assinar.append(assinatura)

    return render(
        request,
        "pagamentos/painel_assinaturas.html",
        {
            "meus_documentos": meus_documentos,
            "para_assinar": para_assinar,
        },
    )


@require_POST
def disparar_assinatura_view(request, assinatura_id):
    """Dispara um rascunho de assinatura para a Autentique via POST."""
    assinatura = get_object_or_404(AssinaturaAutentique, id=assinatura_id, status="RASCUNHO")

    if assinatura.criador != request.user:
        raise PermissionDenied("Apenas o criador do documento pode disparar esta assinatura.")

    try:
        disparar_assinatura_rascunho_com_signatarios(assinatura)
        messages.success(request, "Documento enviado para assinatura com sucesso!")
    except AssinaturaSignatariosError as exc:
        messages.error(request, str(exc))
        return redirect("painel_assinaturas")
    except (OSError, RuntimeError, TypeError, ValueError):
        logger.exception("Erro ao disparar assinatura %s para Autentique", assinatura_id)
        assinatura.status = "ERRO"
        assinatura.save(update_fields=["status"])
        messages.error(request, "Erro ao enviar para o Autentique. Tente novamente.")

    return redirect("painel_assinaturas")
