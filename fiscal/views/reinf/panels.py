"""Views de painel para EFD-Reinf."""

from datetime import date

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render

from fiscal.services import get_serie_2000_data, get_serie_4000_data

from .shared import parse_competencia


@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def painel_reinf_view(request):
    """Renderiza painel EFD-Reinf com filtros por competencia."""
    today = date.today()
    mes, ano, todos = parse_competencia(request, allow_all=True)

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
