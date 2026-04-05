"""Utilitários de mesclagem de PDF usados no backoffice financeiro."""

import io

from pypdf import PdfReader, PdfWriter


def split_pdf_to_temp_pages(arquivo_pdf):
    """Proxy para o helper de divisão de páginas no módulo de extractors."""
    from .pdf_extractors import split_pdf_to_temp_pages as _split

    return _split(arquivo_pdf)


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
    """Mescla a primeira página do canvas sobre o template e retorna BytesIO.

    Se ``template_path`` for inválido/ausente, retorna apenas a página do canvas.
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


__all__ = [
    "mesclar_pdfs_em_memoria",
    "merge_canvas_with_template",
    "split_pdf_to_temp_pages",
]
