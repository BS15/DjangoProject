import io
import os

from django.conf import settings
from pypdf import PdfReader, PdfWriter
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
        self.canvas = canvas.Canvas(self.packet)
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
