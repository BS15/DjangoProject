"""PDF creation, drawing and merging utilities.

Strictly for *writing* PDFs. Imports: reportlab, pypdf.
"""

import io
from datetime import datetime

from pypdf import PdfWriter, PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def mesclar_pdfs_em_memoria(lista_arquivos):
    """
    Recebe uma lista de arquivos (podem ser caminhos no disco ou UploadedFiles da RAM)
    e retorna um buffer de memória contendo o PDF mesclado.
    """
    merger = PdfWriter()

    try:
        for arquivo in lista_arquivos:
            if arquivo:
                merger.append(arquivo)

        output_pdf = io.BytesIO()
        merger.write(output_pdf)
        merger.close()
        output_pdf.seek(0)
        return output_pdf

    except Exception as e:
        print(f"Erro na mesclagem de PDFs: {e}")
        return None


def merge_canvas_with_template(canvas_io, template_path):
    """
    Mescla um canvas PDF (BytesIO gerado pelo ReportLab) sobre um template PDF
    (papel timbrado), retornando o PDF final como BytesIO.
    """
    canvas_io.seek(0)
    template_reader = PdfReader(template_path)
    canvas_reader = PdfReader(canvas_io)

    writer = PdfWriter()
    template_page = template_reader.pages[0]
    canvas_page = canvas_reader.pages[0]

    template_page.merge_page(canvas_page)
    writer.add_page(template_page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output


def gerar_termo_auditoria(processo, usuario_nome="Conselheiro Fiscal"):
    """Gera uma folha de rosto em PDF na memória atestando o fechamento."""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Cabeçalho
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2.0, height - 100, "TERMO DE ENCERRAMENTO E AUDITORIA FISCAL")

    # Dados do Processo
    p.setFont("Helvetica", 12)
    p.drawString(100, height - 160, f"Processo Nº: {processo.id}")
    p.drawString(100, height - 180, f"Credor: {processo.credor}")
    p.drawString(100, height - 200, f"Valor Consolidado: R$ {processo.valor_liquido}")
    p.drawString(100, height - 220, f"Data/Hora do Fechamento: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    # Declaração
    texto_declaracao = (
        "Certifico que os documentos anexos a este processo foram conferidos em sua "
        "integralidade, consolidados em arquivo único e aprovados pelo Conselho Fiscal, "
        "estando aptos para arquivamento definitivo."
    )
    p.drawString(100, height - 280, texto_declaracao[:90])
    p.drawString(100, height - 300, texto_declaracao[90:])

    # Assinatura
    p.line(150, height - 450, 450, height - 450)
    p.drawCentredString(width / 2.0, height - 470, f"Assinado eletronicamente por: {usuario_nome}")

    # Rodapé de segurança
    p.setFont("Helvetica-Oblique", 8)
    p.drawString(50, 50, "Documento gerado automaticamente pelo System X - Integridade Garantida.")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer
