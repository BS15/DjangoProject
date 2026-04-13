"""Utilitarios compartilhados para views de EFD-Reinf."""

import io
import zipfile
from datetime import date

from django.http import HttpResponse


def parse_competencia(request, *, allow_all=False):
    """Retorna (mes, ano, todos) com fallback para a data atual."""
    today = date.today()
    todos = allow_all and request.GET.get("todos") == "1"

    if todos:
        return None, None, True

    try:
        mes = int(request.GET.get("mes", today.month))
        ano = int(request.GET.get("ano", today.year))
        if not (1 <= mes <= 12):
            raise ValueError
    except (ValueError, TypeError):
        mes = today.month
        ano = today.year

    return mes, ano, False


def build_zip_response(xmls, mes, ano):
    """Empacota XMLs em zip e devolve HttpResponse para download."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for filename, xml_content in xmls.items():
            zip_file.writestr(filename, xml_content)

    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type="application/zip")
    zip_filename = f"lotes_reinf_{ano}{mes:02d}.zip"
    response["Content-Disposition"] = f'attachment; filename="{zip_filename}"'
    return response
