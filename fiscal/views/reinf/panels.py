"""Views de painel para EFD-Reinf."""
from decimal import Decimal

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.utils import timezone

from fiscal.services import get_serie_2000_data, get_serie_4000_data
from fiscal.models import RetencaoImposto

from .shared import parse_competencia


@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def painel_reinf_view(request):
    """Renderiza command center da EFD-Reinf por competência."""
    now = timezone.localtime()
    mes, ano, _ = parse_competencia(request, allow_all=False)

    competencia_atual = f"{mes:02d}/{ano}"
    competencia_date = timezone.datetime(year=ano, month=mes, day=1).date()

    retencoes_competencia = RetencaoImposto.objects.filter(competencia=competencia_date).select_related("codigo")
    base_total = sum((ret.rendimento_tributavel or Decimal("0")) for ret in retencoes_competencia)
    irrf_total = sum(
        (ret.valor or Decimal("0"))
        for ret in retencoes_competencia
        if ret.codigo and (ret.codigo.codigo or "").upper().startswith("IR")
    )
    csrf_total = sum(
        (ret.valor or Decimal("0"))
        for ret in retencoes_competencia
        if ret.codigo and not (ret.codigo.codigo or "").upper().startswith("IR")
    )

    serie_2000 = get_serie_2000_data(mes, ano)
    serie_4000 = get_serie_4000_data(mes, ano)
    eventos_prontos = []

    for grupo in serie_2000:
        eventos_prontos.append({
            "tipo_evento": "R-2010",
            "credor_nome": getattr(grupo.get("credor"), "nome", "Credor não informado"),
            "data_geracao": now,
            "numero_recibo": None,
        })
    for grupo in serie_4000:
        eventos_prontos.append({
            "tipo_evento": grupo.get("evento", "R-4020"),
            "credor_nome": getattr(grupo.get("beneficiario"), "nome", "Beneficiário não informado"),
            "data_geracao": now,
            "numero_recibo": None,
        })

    context = {
        "competencia_atual": competencia_atual,
        "resumo_valores": {
            "base_total": base_total,
            "irrf_total": irrf_total,
            "csrf_total": csrf_total,
        },
        "eventos_prontos": eventos_prontos,
    }
    return render(request, "fiscal/painel_reinf.html", context)
