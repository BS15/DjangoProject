"""Servicos compartilhados de documentos e assinaturas para os apps modulares."""

from commons.shared.integracoes.autentique import enviar_documento_para_assinatura
from commons.shared.pdf_tools import gerar_documento_pdf
from django.http import HttpResponse


class AssinaturaSignatariosError(ValueError):
	"""Erro de validação quando não há signatários válidos para envio."""


def gerar_documento_bytes(doc_type, obj, document_registry=None, **kwargs):
	"""Gera PDF de documento usando document_registry apropriado."""
	if document_registry is None:
		from fluxo.pdf_generators import FLUXO_DOCUMENT_REGISTRY

		document_registry = FLUXO_DOCUMENT_REGISTRY
	return gerar_documento_pdf(doc_type, obj, document_registry, **kwargs)


def montar_resposta_pdf(pdf_bytes, nome_arquivo, inline=True):
	disposition = "inline" if inline else "attachment"
	if hasattr(pdf_bytes, "read"):
		try:
			pdf_bytes.seek(0)
		except (AttributeError, OSError):
			pass
		content = pdf_bytes.read()
	else:
		content = pdf_bytes
	response = HttpResponse(content, content_type="application/pdf")
	response["Content-Disposition"] = f'{disposition}; filename="{nome_arquivo}"'
	return response


def gerar_resposta_pdf(doc_type, obj, nome_arquivo, inline=True, **kwargs):
	pdf_bytes = gerar_documento_bytes(doc_type, obj, **kwargs)
	return montar_resposta_pdf(pdf_bytes, nome_arquivo, inline=inline)


def criar_assinatura_rascunho(entidade, tipo_documento, criador, pdf_bytes, nome_arquivo):
	"""Cria um registro AssinaturaAutentique em status RASCUNHO com o PDF gerado."""
	from django.contrib.contenttypes.models import ContentType
	from django.core.files.base import ContentFile
	from fluxo.domain_models import AssinaturaAutentique

	ct = ContentType.objects.get_for_model(entidade)
	instancia = AssinaturaAutentique(
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
















