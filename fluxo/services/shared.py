"""Servicos compartilhados de documentos para os apps modulares."""

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.http import HttpResponse

from fluxo.pdf_generators import gerar_documento_pdf


class AssinaturaSignatariosError(Exception):
	"""Erro de signatarios para envio/sincronizacao de assinatura."""


def gerar_documento_bytes(doc_type, obj, **kwargs):
	return gerar_documento_pdf(doc_type, obj, **kwargs)


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
	from fluxo.models import AssinaturaAutentique

	assinatura = AssinaturaAutentique(
		content_type=ContentType.objects.get_for_model(entidade),
		object_id=entidade.id,
		tipo_documento=tipo_documento,
		criador=criador,
		status="RASCUNHO",
	)
	assinatura.arquivo.save(nome_arquivo, ContentFile(pdf_bytes), save=True)
	return assinatura


def construir_signatarios_padrao(entidade, extra_emails=None):
	if entidade is None:
		return []

	campos_prioritarios = (
		"beneficiario",
		"proponente",
		"credor",
		"suprido",
		"solicitante",
		"fiscal_contrato",
		"criador",
		"aprovado_por_supervisor",
		"aprovado_por_ordenador",
		"aprovado_por_conselho",
	)

	emails = []
	for campo in campos_prioritarios:
		candidato = getattr(entidade, campo, None)
		email = getattr(candidato, "email", None) if candidato else None
		if email:
			emails.append(email)

	if extra_emails:
		for email in extra_emails:
			if email:
				emails.append(email)

	vistos = set()
	signatarios = []
	for email in emails:
		if email in vistos:
			continue
		vistos.add(email)
		signatarios.append({"email": email, "action": "SIGN"})

	return signatarios


def enviar_para_assinatura(entidade, tipo_documento, nome_doc, signatarios, doc_type=None, pdf_bytes=None, **kwargs):
	from fluxo.models import AssinaturaAutentique
	from fluxo.services.integracoes.autentique import enviar_documento_para_assinatura

	ct = ContentType.objects.get_for_model(entidade)
	assinatura_existente = AssinaturaAutentique.objects.filter(
		content_type=ct,
		object_id=entidade.pk,
		tipo_documento=tipo_documento,
		status="PENDENTE",
	).first()
	if assinatura_existente:
		return assinatura_existente

	if pdf_bytes is None:
		if not doc_type:
			raise ValueError("doc_type e obrigatorio quando pdf_bytes nao for informado.")
		pdf_bytes = gerar_documento_bytes(doc_type, entidade, **kwargs)

	resultado = enviar_documento_para_assinatura(pdf_bytes, nome_doc, signatarios)

	return AssinaturaAutentique.objects.create(
		content_type=ct,
		object_id=entidade.pk,
		tipo_documento=tipo_documento,
		autentique_id=resultado["id"],
		autentique_url=resultado["url"],
		dados_signatarios=resultado["signers_data"],
		status="PENDENTE",
	)


def disparar_assinatura_rascunho_com_signatarios(assinatura):
	"""Envia um rascunho de assinatura existente para a Autentique com signatários padrão."""
	model_cls = assinatura.content_type.model_class()
	entidade = model_cls.objects.filter(pk=assinatura.object_id).first()
	if entidade is None:
		raise ValueError("Entidade de assinatura não encontrada.")

	signatarios = construir_signatarios_padrao(entidade)
	if not signatarios:
		raise AssinaturaSignatariosError("Nenhum signatário com e-mail válido foi encontrado.")

	from fluxo.services.integracoes.autentique import enviar_documento_para_assinatura

	with assinatura.arquivo.open("rb") as arquivo_pdf:
		resultado = enviar_documento_para_assinatura(
			arquivo_pdf.read(),
			assinatura.tipo_documento,
			signatarios,
		)

	assinatura.autentique_id = resultado["id"]
	assinatura.autentique_url = resultado["url"]
	assinatura.dados_signatarios = resultado["signers_data"]
	assinatura.status = "PENDENTE"
	assinatura.save(update_fields=["autentique_id", "autentique_url", "dados_signatarios", "status"])
	return assinatura


def sincronizar_assinatura(assinatura):
	from fluxo.services.integracoes.autentique import verificar_e_baixar_documento

	if assinatura.status == "ASSINADO":
		return "already_signed"

	resultado = verificar_e_baixar_documento(assinatura.autentique_id)
	if not resultado["assinado"]:
		return "pending"

	nome_arquivo = f"{assinatura.tipo_documento}_Assinado_{assinatura.id}.pdf"
	assinatura.arquivo_assinado.save(nome_arquivo, ContentFile(resultado["pdf_bytes"]), save=False)
	assinatura.status = "ASSINADO"
	assinatura.save()
	return "signed"

