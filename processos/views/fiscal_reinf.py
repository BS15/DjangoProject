"""Views do painel EFD-Reinf."""

from datetime import date

from django.http import HttpResponse
from django.shortcuts import render


def painel_reinf_view(request):
    """
    Painel EFD-Reinf - exibe as retencoes separadas em:
      - Serie 2000 (INSS / R-2010)
      - Serie 4000 (IRRF / CSRF / R-4010 / R-4020)

    Aceita os parametros GET mes (1-12) e ano (YYYY) para filtrar
    pela competencia. Quando omitidos, usa o mes/ano corrente.
    O parametro todos=1 ignora o filtro de competencia e retorna
    todos os lancamentos de todas as competencias.
    """
    from ..reinf_services import get_serie_2000_data, get_serie_4000_data

    today = date.today()
    todos = request.GET.get("todos") == "1"

    if todos:
        mes = None
        ano = None
    else:
        try:
            mes = int(request.GET.get("mes", today.month))
            ano = int(request.GET.get("ano", today.year))
            if not (1 <= mes <= 12):
                raise ValueError
        except (ValueError, TypeError):
            mes = today.month
            ano = today.year

    serie_2000 = get_serie_2000_data(mes, ano)
    serie_4000 = get_serie_4000_data(mes, ano)

    context = {
        "mes": mes if mes is not None else today.month,
        "ano": ano if ano is not None else today.year,
        "todos": todos,
        "serie_2000": serie_2000,
        "serie_4000": serie_4000,
        "meses": range(1, 13),
        "anos": range(today.year - 4, today.year + 2),
    }
    return render(request, "fiscal/painel_reinf.html", context)


def gerar_lote_reinf_view(request):
    """
    Generate EFD-Reinf XML batch files (lotes) for R-2010 (INSS) and
    R-4020 (Federais) based on the given competencia (mes/ano) and return
    them packaged as a downloadable .zip file.

    GET parameters:
    - mes: month 1-12 (defaults to current month)
    - ano: year YYYY (defaults to current year)

    Returns 404 if no attested retentions exist for the requested period.
    """
    import io
    import zipfile

    from ..reinf_services import gerar_lotes_reinf

    today = date.today()
    try:
        mes = int(request.GET.get("mes", today.month))
        ano = int(request.GET.get("ano", today.year))
        if not (1 <= mes <= 12):
            raise ValueError
    except (ValueError, TypeError):
        mes = today.month
        ano = today.year

    try:
        xmls = gerar_lotes_reinf(mes, ano)
    except ValueError as exc:
        return HttpResponse(str(exc), status=404)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, xml_content in xmls.items():
            zf.writestr(filename, xml_content)

    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type="application/zip")
    zip_filename = f"lotes_reinf_{ano}{mes:02d}.zip"
    response["Content-Disposition"] = f'attachment; filename="{zip_filename}"'
    return response
