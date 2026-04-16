"""Views de acoes para EFD-Reinf."""

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from fiscal.services import gerar_lotes_reinf

from .shared import build_zip_response, parse_competencia


def _parse_competencia_post(request: HttpRequest) -> tuple[int, int]:
    competencia = (request.POST.get("competencia") or "").strip()
    if competencia:
        try:
            if "/" in competencia:
                mes_str, ano_str = competencia.split("/", 1)
                mes = int(mes_str)
                ano = int(ano_str)
            elif "-" in competencia:
                ano_str, mes_str = competencia.split("-", 1)
                mes = int(mes_str)
                ano = int(ano_str)
            else:
                raise ValueError
            if 1 <= mes <= 12:
                return mes, ano
        except (ValueError, TypeError):
            pass

    today = date.today()
    return today.month, today.year


@require_POST
@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def gerar_lote_reinf_action(request: HttpRequest) -> HttpResponse:
    """Gera e devolve zip com lotes XML da EFD-Reinf para a competência."""
    mes, ano = _parse_competencia_post(request)

    try:
        xmls = gerar_lotes_reinf(mes, ano)
    except ValueError as exc:
        return HttpResponse(str(exc), status=404)

    return build_zip_response(xmls, mes, ano)


@require_POST
@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def transmitir_lote_reinf_action(request: HttpRequest) -> HttpResponse:
    """Placeholder de transmissão para ambiente externo da Receita."""
    messages.warning(request, "Transmissão para e-CAC ainda não está habilitada neste ambiente.")
    return redirect("painel_reinf_view")


@require_POST
@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def gerar_lote_reinf_legacy_action(request: HttpRequest) -> HttpResponse:
    """Alias legado para geração de lote por GET."""
    mes, ano, _ = parse_competencia(request)
    try:
        xmls = gerar_lotes_reinf(mes, ano)
    except ValueError as exc:
        return HttpResponse(str(exc), status=404)
    return build_zip_response(xmls, mes, ano)


__all__ = [
    "gerar_lote_reinf_action",
    "transmitir_lote_reinf_action",
    "gerar_lote_reinf_legacy_action",
]
