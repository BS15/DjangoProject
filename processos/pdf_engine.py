import io
import os
import textwrap

from django.conf import settings
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


class BasePDFDocument:
    """
    Base class for PDF document generation using the Strategy Pattern.

    Subclasses override ``draw_content`` to render their specific document
    layout onto ``self.canvas``.  ``generate`` then merges the result with
    the organisation letterhead and returns the final PDF bytes.
    """

    def __init__(self, obj, letterhead_path=None):
        self.obj = obj  # The database instance (Processo, Diaria, etc.)
        self.packet = io.BytesIO()
        self.canvas = canvas.Canvas(self.packet, pagesize=A4)
        self.page_width, self.page_height = A4
        self.letterhead_path = letterhead_path or getattr(settings, 'CRECI_LETTERHEAD_PATH', None)

    def draw_content(self):
        """To be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement draw_content()")

    def generate(self):
        """
        Renders the document content, merges it with the letterhead template
        and returns the final PDF as bytes.
        """
        # 1. Draw specific content
        self.draw_content()
        self.canvas.save()
        self.packet.seek(0)

        # 2. Merge with letterhead
        new_pdf = PdfReader(self.packet)
        template_path = os.path.join(settings.BASE_DIR, self.letterhead_path)
        with open(template_path, "rb") as f:
            template_pdf = PdfReader(f)
            page = template_pdf.pages[0]
            page.merge_page(new_pdf.pages[0])

            # 3. Write final output
            output = PdfWriter()
            output.add_page(page)
            final_packet = io.BytesIO()
            output.write(final_packet)

        return final_packet.getvalue()


class TermoContabilizacaoDocument(BasePDFDocument):
    """Generates the 'Termo de Contabilização' PDF for a given Processo."""

    def draw_content(self):
        processo = self.obj
        c = self.canvas
        page_width = self.page_width

        # --- Header ---
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(page_width / 2, 750, "TERMO DE CONTABILIZAÇÃO")

        # --- Process Details ---
        c.setFont("Helvetica", 11)
        line_height = 20
        y = 700
        credor_nome = processo.credor.nome if processo.credor else "N/A"
        details = [
            f"Processo Nº: {processo.id}",
            f"Nota de Empenho: {processo.n_nota_empenho or 'N/A'}",
            f"Credor: {credor_nome}",
            f"Valor Consolidado: R$ {processo.valor_liquido}",
        ]
        for line in details:
            c.drawString(72, y, line)
            y -= line_height

        # --- Declaration Text ---
        declaration = (
            "Certifico que a despesa referente ao Processo acima identificado foi devidamente "
            "registrada e contabilizada no sistema financeiro nesta data, em estrita conformidade "
            "com as normas contábeis e a legislação vigente."
        )
        c.setFont("Helvetica", 11)
        wrapped_lines = textwrap.wrap(declaration, width=85)
        y = 600
        for line in wrapped_lines:
            c.drawString(72, y, line)
            y -= line_height

        # --- Signature Block ---
        sig_x = page_width / 2
        c.line(sig_x - 120, 320, sig_x + 120, 320)
        c.setFont("Helvetica", 11)
        c.drawCentredString(sig_x, 305, "Assinatura do(a) Contador(a)")
        c.drawCentredString(sig_x, 280, "Data da Contabilização: _____ / _____ / _________")


class TermoAtesteDocument(BasePDFDocument):
    """Generates the 'Termo de Liquidação e Ateste' PDF for a given DocumentoFiscal."""

    def draw_content(self):
        documento_fiscal = self.obj
        c = self.canvas
        page_width = self.page_width

        # --- Header ---
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(page_width / 2, 750, "TERMO DE LIQUIDAÇÃO E ATESTE")

        # --- Invoice Details ---
        c.setFont("Helvetica", 11)
        line_height = 20
        y = 700

        processo_id = (
            documento_fiscal.processo.id if documento_fiscal.processo else "N/A"
        )
        fornecedor = (
            documento_fiscal.processo.credor.nome
            if documento_fiscal.processo and documento_fiscal.processo.credor
            else "N/A"
        )
        details = [
            f"Processo Nº: {processo_id}",
            f"Documento Fiscal / Nota Nº: {documento_fiscal.numero_nota_fiscal}",
            f"Fornecedor: {fornecedor}",
            f"Valor do Documento: R$ {documento_fiscal.valor_bruto}",
        ]
        for line in details:
            c.drawString(72, y, line)
            y -= line_height

        # --- Declaration Text ---
        declaration = (
            "Atesto, para os devidos fins e sob as penas da lei, que os serviços referenciados "
            "no documento fiscal supra foram efetivamente prestados, ou os materiais entregues, "
            "de forma satisfatória e de acordo com as especificações contratuais exigidas."
        )
        c.setFont("Helvetica", 11)
        wrapped_lines = textwrap.wrap(declaration, width=85)
        y = 600
        for line in wrapped_lines:
            c.drawString(72, y, line)
            y -= line_height

        # --- Signature Block ---
        sig_x = page_width / 2
        if documento_fiscal.fiscal_contrato:
            fiscal_name = documento_fiscal.fiscal_contrato.get_full_name()
        else:
            fiscal_name = "Fiscal Não Atribuído"
        c.setFont("Helvetica", 11)
        c.drawCentredString(sig_x, 335, fiscal_name)
        c.line(sig_x - 120, 320, sig_x + 120, 320)
        c.drawCentredString(sig_x, 305, "Fiscal do Contrato")
        c.drawCentredString(sig_x, 280, "Local e Data: Florianópolis, _____ / _____ / _________")


DOCUMENT_REGISTRY = {
    'contabilizacao': TermoContabilizacaoDocument,
    'ateste': TermoAtesteDocument,
}
