"""Views de acoes para EFD-Reinf."""

from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse

from fiscal.services import gerar_lotes_reinf

from .shared import build_zip_response, parse_competencia


@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def gerar_lote_reinf_view(request):
    """Gera e devolve zip com lotes XML da EFD-Reinf para a competencia."""
    mes, ano, _ = parse_competencia(request)

    try:
        xmls = gerar_lotes_reinf(mes, ano)
    except ValueError as exc:
        return HttpResponse(str(exc), status=404)

    return build_zip_response(xmls, mes, ano)
