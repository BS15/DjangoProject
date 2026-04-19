"""Views de integração com assinaturas Autentique para diárias."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect

from commons.shared.integracoes.autentique import (
    enviar_documento_para_assinatura,
    verificar_e_baixar_documento,
)
from fluxo.domain_models import AssinaturaAutentique
from verbas_indenizatorias.models import Diaria


@permission_required("verbas_indenizatorias.pode_gerenciar_diarias", raise_exception=True)
def sincronizar_assinatura_view(request, assinatura_id):
    """Sincroniza o estado de uma assinatura e baixa o PDF assinado quando disponível."""
    assinatura = get_object_or_404(AssinaturaAutentique, id=assinatura_id)
    diaria_id = assinatura.object_id

    if not assinatura.autentique_id:
        messages.warning(request, "Assinatura ainda não foi enviada para a Autentique.")
        return redirect("gerenciar_diaria", pk=diaria_id)

    try:
        status = verificar_e_baixar_documento(assinatura.autentique_id)
        if status.get("assinado"):
            assinatura.status = "ASSINADO"
            pdf_bytes = status.get("pdf_bytes")
            if pdf_bytes:
                from django.core.files.base import ContentFile

                assinatura.arquivo_assinado.save(
                    f"ASSINADO_{assinatura.tipo_documento}_{assinatura.id}.pdf",
                    ContentFile(pdf_bytes),
                    save=False,
                )
            assinatura.save(update_fields=["status", "arquivo_assinado"])
            messages.success(request, "Documento assinado sincronizado com sucesso.")
        else:
            assinatura.status = "PENDENTE"
            assinatura.save(update_fields=["status"])
            messages.info(request, "Documento ainda pendente de assinatura na Autentique.")
    except Exception as exc:
        assinatura.status = "ERRO"
        assinatura.save(update_fields=["status"])
        messages.error(request, f"Falha ao sincronizar assinatura: {exc}")

    return redirect("gerenciar_diaria", pk=diaria_id)


@permission_required("verbas_indenizatorias.pode_gerenciar_diarias", raise_exception=True)
def reenviar_assinatura_view(request, diaria_id):
    """Reenvia o rascunho SCD da diária para assinatura na Autentique."""
    diaria = get_object_or_404(Diaria, id=diaria_id)
    assinatura = diaria.assinaturas_autentique.filter(tipo_documento="SCD").order_by("-criado_em").first()

    if not assinatura or not assinatura.arquivo:
        messages.warning(request, "Nenhum rascunho de assinatura SCD encontrado para reenvio.")
        return redirect("gerenciar_diaria", pk=diaria.id)

    try:
        assinatura.arquivo.open("rb")
        payload = enviar_documento_para_assinatura(
            assinatura.arquivo.read(),
            f"SCD_Diaria_{diaria.id}",
            signatarios=[],
        )
        assinatura.autentique_id = payload.get("id")
        assinatura.autentique_url = payload.get("url") or ""
        assinatura.dados_signatarios = payload.get("signers_data") or {}
        assinatura.status = "PENDENTE"
        assinatura.save(update_fields=["autentique_id", "autentique_url", "dados_signatarios", "status"])
        messages.success(request, "Documento reenviado para assinatura com sucesso.")
    except Exception as exc:
        assinatura.status = "ERRO"
        assinatura.save(update_fields=["status"])
        messages.error(request, f"Falha ao reenviar assinatura: {exc}")
    finally:
        try:
            assinatura.arquivo.close()
        except Exception:
            pass

    return redirect("gerenciar_diaria", pk=diaria.id)


__all__ = ["sincronizar_assinatura_view", "reenviar_assinatura_view"]
