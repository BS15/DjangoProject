"""
Ferramentas genéricas para geração e manipulação de PDFs.
Utilizadas por múltiplos apps (fluxo, verbas_indenizatorias, suprimentos, etc).
"""

"""Ferramentas utilitárias para manipulação e geração de PDFs compartilhados.

Este módulo implementa classes e funções base para geração de documentos PDF reutilizáveis em múltiplos domínios.
"""
import io
import logging
import os
import textwrap
from datetime import date

from django.conf import settings
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


logger = logging.getLogger(__name__)
_CHAR_WIDTH_RATIO = 0.55


def _draw_wrapped_text(p, text, x, y, max_width, font_name="Helvetica", font_size=11, leading=16):
	"""
	Desenha texto com quebra automática de linha no canvas ReportLab.
	Retorna a posição Y após o último texto desenhado.
	"""
	if not text:
		return y
	p.setFont(font_name, font_size)
	chars_per_line = max(1, int(max_width / (font_size * _CHAR_WIDTH_RATIO)))
	lines = textwrap.wrap(str(text), width=chars_per_line)
	if not lines:
		lines = [str(text)]
	for line in lines:
		p.drawString(x, y, line)
		y -= leading
	return y


def _contar_paginas_documentos(processo):
	"""
	Conta o número total de documentos e páginas nos DocumentoProcesso em PDF.
	Retorna uma tupla (total_documentos, total_paginas).
	"""
	total_docs = 0
	total_pages = 0

	for doc in processo.documentos.all():
		total_docs += 1
		try:
			with doc.arquivo.open('rb') as f:
				reader = PdfReader(f)
				total_pages += len(reader.pages)
		except (FileNotFoundError, OSError, ValueError) as exc:
			logger.warning(
				"Não foi possível contar páginas do documento %s do processo %s: %s",
				getattr(doc, "id", None),
				processo.id,
				exc,
			)

	return total_docs, total_pages


def merge_canvas_with_template(canvas_io, template_path):
	"""
	Mescla canvas renderizado com timbrado (template) PDF.
	Retorna BytesIO com PDF final.
	"""
	canvas_io.seek(0)
	canvas_reader = PdfReader(canvas_io)
	canvas_page = canvas_reader.pages[0]

	writer = PdfWriter()
	if template_path:
		try:
			with open(template_path, "rb") as template_file:
				template_reader = PdfReader(template_file)
				template_page = template_reader.pages[0]
				template_page.merge_page(canvas_page)
				writer.add_page(template_page)
		except FileNotFoundError:
			writer.add_page(canvas_page)
	else:
		writer.add_page(canvas_page)

	output = io.BytesIO()
	writer.write(output)
	output.seek(0)
	return output


class BasePDFDocument:
	"""
	Classe base para geração de documentos PDF no padrão Strategy.

	Subclasses devem sobrescrever ``draw_content`` para desenhar o layout no
	canvas e usar ``generate`` para obter o PDF final em bytes.
	"""

	def __init__(self, obj, letterhead_path=None, **kwargs):
		"""Inicializa contexto de renderização para a entidade informada."""
		self.obj = obj
		self.packet = io.BytesIO()
		self.canvas = canvas.Canvas(self.packet, pagesize=A4)
		self.page_width, self.page_height = A4
		self.letterhead_path = letterhead_path or getattr(settings, 'CRECI_LETTERHEAD_PATH', None)
		self.kwargs = kwargs

	def draw_content(self):
		"""Desenha o conteúdo específico do documento no canvas atual."""
		raise NotImplementedError("Subclasses must implement draw_content()")

	def generate(self):
		"""Renderiza o conteúdo e retorna o PDF final mesclado ao timbrado."""
		self.draw_content()
		self.canvas.save()
		template_path = None
		if self.letterhead_path:
			template_path = os.path.join(settings.BASE_DIR, self.letterhead_path)
			if not os.path.exists(template_path):
				logger.warning(
					"Letterhead file not found at '%s'. Generating PDF without letterhead.",
					template_path,
				)
				template_path = None

		merged_packet = merge_canvas_with_template(self.packet, template_path)
		return merged_packet.getvalue()


def gerar_documento_pdf(doc_type, obj, document_registry, **kwargs):
	"""
	Factory genérica: instancia a classe de documento adequada e retorna o PDF em bytes.
	
	Args:
		doc_type: tipo de documento (string, ex: 'scd', 'pcd')
		obj: objeto de domínio (Diaria, Processo, etc)
		document_registry: dicionário mapeando tipos para classes de documento
		**kwargs: argumentos adicionais passados ao construtor do documento
	
	Returns:
		bytes: conteúdo do PDF
		
	Raises:
		ValueError: se doc_type não estiver no registry
	"""
	doc_class = document_registry.get(doc_type.lower())
	if not doc_class:
		raise ValueError(f"Tipo de documento '{doc_type}' não reconhecido.")
	documento = doc_class(obj, **kwargs)
	return documento.generate()


__all__ = [
	"_draw_wrapped_text",
	"_contar_paginas_documentos",
	"merge_canvas_with_template",
	"BasePDFDocument",
	"gerar_documento_pdf",
]
