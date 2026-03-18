"""
reinf_services.py

Aggregation logic for the EFD-Reinf panel (ReinfPanelView).

Série 2000 – Previdenciário (INSS / R-2010)
--------------------------------------------
Groups RetencaoImposto records whose CodigosImposto.serie_reinf == 'S2000'
by:  Credor (prestador / emitente da NF)  →  DocumentoFiscal  →  [retencoes]

Série 4000 – Retenções Federais (IRRF / CSRF / R-4010 / R-4020)
-----------------------------------------------------------------
Groups RetencaoImposto records whose CodigosImposto.serie_reinf == 'S4000'
by:  Credor (beneficiário)  →  Natureza do Rendimento (Tabela 01)  →  [retencoes]
"""

from collections import defaultdict
from datetime import date

from .models import RetencaoImposto


def _build_competencia_date(month: int, year: int) -> date:
    """Return the first-day-of-month Date used internally as competência."""
    return date(year, month, 1)


def get_serie_2000_data(month: int | None, year: int | None) -> list:
    """
    Return aggregated data for Série 2000 (INSS / R-2010).

    When *month* and *year* are both ``None`` all entries are returned
    regardless of competência (clear-filter / show-all mode).

    Structure returned:
    [
      {
        "credor": <Credor instance>,           # Prestador (emitente da NF)
        "notas": [
          {
            "nota_fiscal": <DocumentoFiscal>,
            "retencoes": [<RetencaoImposto>, ...],
            "total_bruto":  <Decimal>,
            "total_base":   <Decimal>,
            "total_retido": <Decimal>,
          },
          ...
        ],
        "total_retido": <Decimal>,
      },
      ...
    ]
    """
    qs = RetencaoImposto.objects.filter(codigo__serie_reinf='S2000')
    if month is not None and year is not None:
        competencia = _build_competencia_date(month, year)
        qs = qs.filter(competencia=competencia)

    retencoes = (
        qs
        .select_related(
            'nota_fiscal',
            'nota_fiscal__nome_emitente',
            'codigo',
            'beneficiario',
        )
        .order_by(
            'nota_fiscal__nome_emitente__nome',
            'nota_fiscal__data_emissao',
            'nota_fiscal__id',
        )
    )

    # --- group: credor → nf → retencoes ---
    credor_map: dict = defaultdict(lambda: defaultdict(list))
    for r in retencoes:
        credor = r.nota_fiscal.nome_emitente
        nf = r.nota_fiscal
        credor_map[credor][nf].append(r)

    result = []
    for credor, nf_map in credor_map.items():
        credor_total_retido = 0
        notas = []
        for nf, rets in nf_map.items():
            total_bruto = nf.valor_bruto or 0
            total_base = sum((r.rendimento_tributavel or 0) for r in rets)
            total_retido = sum((r.valor or 0) for r in rets)
            credor_total_retido += total_retido
            notas.append({
                'nota_fiscal': nf,
                'retencoes': rets,
                'total_bruto': total_bruto,
                'total_base': total_base,
                'total_retido': total_retido,
            })
        result.append({
            'credor': credor,
            'notas': notas,
            'total_retido': credor_total_retido,
        })

    return result


def get_serie_4000_data(month: int | None, year: int | None) -> list:
    """
    Return aggregated data for Série 4000 (IRRF / CSRF / R-4010 / R-4020).

    When *month* and *year* are both ``None`` all entries are returned
    regardless of competência (clear-filter / show-all mode).

    Structure returned:
    [
      {
        "beneficiario": <Credor instance>,
        "evento": "R-4010" | "R-4020",     # derived from credor.tipo
        "naturezas": [
          {
            "natureza_codigo": "15001",     # Tabela 01 do SPED
            "retencoes": [<RetencaoImposto>, ...],
            "total_bruto":  <Decimal>,
            "total_retido": <Decimal>,
          },
          ...
        ],
        "total_retido": <Decimal>,
      },
      ...
    ]
    """
    qs = RetencaoImposto.objects.filter(codigo__serie_reinf='S4000')
    if month is not None and year is not None:
        competencia = _build_competencia_date(month, year)
        qs = qs.filter(competencia=competencia)

    retencoes = (
        qs
        .select_related(
            'nota_fiscal',
            'nota_fiscal__nome_emitente',
            'beneficiario',
            'codigo',
        )
        .order_by(
            'beneficiario__nome',
            'codigo__natureza_rendimento',
            'competencia',
        )
    )

    # --- group: beneficiario → natureza → retencoes ---
    benef_map: dict = defaultdict(lambda: defaultdict(list))
    for r in retencoes:
        beneficiario = r.beneficiario
        natureza = r.codigo.natureza_rendimento or 'Não informado'
        benef_map[beneficiario][natureza].append(r)

    result = []
    for beneficiario, natureza_map in benef_map.items():
        benef_total_retido = 0
        naturezas = []
        for natureza, rets in natureza_map.items():
            total_bruto = sum((r.rendimento_tributavel or 0) for r in rets)
            total_retido = sum((r.valor or 0) for r in rets)
            benef_total_retido += total_retido
            naturezas.append({
                'natureza_codigo': natureza,
                'retencoes': rets,
                'total_bruto': total_bruto,
                'total_retido': total_retido,
            })
        # Determine event type: R-4010 (PF) or R-4020 (PJ)
        evento = 'R-4010' if (beneficiario and beneficiario.tipo == 'PF') else 'R-4020'
        result.append({
            'beneficiario': beneficiario,
            'evento': evento,
            'naturezas': naturezas,
            'total_retido': benef_total_retido,
        })

    return result
