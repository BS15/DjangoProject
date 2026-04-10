"""Servicos compartilhados de documentos para os apps modulares."""


from django.http import HttpResponse
from commons.shared.pdf_tools import gerar_documento_pdf






def gerar_documento_bytes(doc_type, obj, document_registry=None, **kwargs):
	"""
	Gera PDF de documento usando document_registry apropriado.
	Se não fornecido, usa o document_registry do app do objeto.
	"""
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
















