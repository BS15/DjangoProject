"""Serviços transversais para rascunho e disparo de assinaturas."""

from commons.shared.integracoes.autentique import enviar_documento_para_assinatura


class AssinaturaSignatariosError(ValueError):
    """Erro de validação quando não há signatários válidos para envio."""


def criar_assinatura_rascunho(entidade, tipo_documento, criador, pdf_bytes, nome_arquivo, assinatura_model):
    """Cria um registro de assinatura em status RASCUNHO com o PDF gerado."""
    from django.contrib.contenttypes.models import ContentType
    from django.core.files.base import ContentFile

    ct = ContentType.objects.get_for_model(entidade)
    instancia = assinatura_model(
        content_type=ct,
        object_id=entidade.pk,
        tipo_documento=tipo_documento,
        status="RASCUNHO",
    )
    if criador is not None:
        instancia.criador = criador
    instancia.arquivo.save(nome_arquivo, ContentFile(pdf_bytes), save=False)
    instancia.save()
    return instancia


def disparar_assinatura_rascunho_com_signatarios(assinatura):
    """Envia um rascunho para a Autentique e atualiza seus metadados."""
    if not assinatura.arquivo:
        raise AssinaturaSignatariosError("Documento sem arquivo para envio à Autentique.")

    email = assinatura.criador.email if assinatura.criador else ""
    if not email:
        raise AssinaturaSignatariosError("Criador do documento não possui e-mail para assinatura.")

    signatarios = [{"email": email, "action": "SIGN"}]

    assinatura.arquivo.open("rb")
    try:
        payload = enviar_documento_para_assinatura(
            assinatura.arquivo.read(),
            f"{assinatura.tipo_documento}_{assinatura.id}",
            signatarios,
        )
    finally:
        try:
            assinatura.arquivo.close()
        except Exception:
            pass

    assinatura.autentique_id = payload.get("id")
    assinatura.autentique_url = payload.get("url") or ""
    assinatura.dados_signatarios = payload.get("signers_data") or {}
    assinatura.status = "PENDENTE"
    assinatura.save(update_fields=["autentique_id", "autentique_url", "dados_signatarios", "status"])
    return assinatura


__all__ = [
    "AssinaturaSignatariosError",
    "criar_assinatura_rascunho",
    "disparar_assinatura_rascunho_com_signatarios",
]