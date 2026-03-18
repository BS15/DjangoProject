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

import xml.dom.minidom
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date

from .models import RetencaoImposto, DadosContribuinte


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


# ---------------------------------------------------------------------------
# XML batch generation – R-2010 (INSS) and R-4020 (Federais)
# ---------------------------------------------------------------------------

def _build_r2010_xml(cnpj: str, retencoes: list, month: int, year: int) -> str:
    """
    Build a minimal R-2010 (INSS / Série 2000) XML skeleton for a single
    provider CNPJ, listing every retention record for that CNPJ.

    Returns a pretty-printed XML string.
    """
    root = ET.Element(
        'Reinf',
        xmlns='http://www.reinf.esocial.gov.br/schemas/evtServTom/v2_01_01',
    )

    evt = ET.SubElement(root, 'evtServTom')

    ide_evento = ET.SubElement(evt, 'ideEvento')
    ET.SubElement(ide_evento, 'indRetif').text = '1'
    ET.SubElement(ide_evento, 'perApur').text = f'{year}-{month:02d}'
    ET.SubElement(ide_evento, 'tpAmb').text = '2'
    ET.SubElement(ide_evento, 'procEmi').text = '1'
    ET.SubElement(ide_evento, 'verProc').text = '1.0'

    ide_contrib = ET.SubElement(evt, 'ideContrib')
    ET.SubElement(ide_contrib, 'tpInsc').text = '1'
    ET.SubElement(ide_contrib, 'nrInsc').text = cnpj

    ide_estab = ET.SubElement(evt, 'ideEstab')
    ET.SubElement(ide_estab, 'tpInsc').text = '1'
    ET.SubElement(ide_estab, 'nrInsc').text = cnpj

    det_evt = ET.SubElement(ide_estab, 'detEvt')
    for ret in retencoes:
        nf = ret.nota_fiscal
        nf_seq = ET.SubElement(det_evt, 'nfSeq')
        ET.SubElement(nf_seq, 'nrNF').text = str(nf.numero_nota_fiscal or '')
        ET.SubElement(nf_seq, 'dtEmiNF').text = str(nf.data_emissao)
        ET.SubElement(nf_seq, 'vrBruto').text = str(nf.valor_bruto or 0)

        det_ret = ET.SubElement(nf_seq, 'detRet')
        ET.SubElement(det_ret, 'vrBaseRet').text = str(ret.rendimento_tributavel or 0)
        ET.SubElement(det_ret, 'vrRet').text = str(ret.valor or 0)

    raw = ET.tostring(root, encoding='unicode')
    return xml.dom.minidom.parseString(raw).toprettyxml(indent='  ')


def _build_r4020_xml(cnpj: str, retencoes: list, month: int, year: int) -> str:
    """
    Build a minimal R-4020 (Federal taxes / Série 4000) XML skeleton for a
    single provider CNPJ.  Retentions are sub-grouped by *natureza_rendimento*.

    Returns a pretty-printed XML string.
    """
    root = ET.Element(
        'Reinf',
        xmlns='http://www.reinf.esocial.gov.br/schemas/evtRetPJ/v2_01_01',
    )

    evt = ET.SubElement(root, 'evtRetPJ')

    ide_evento = ET.SubElement(evt, 'ideEvento')
    ET.SubElement(ide_evento, 'indRetif').text = '1'
    ET.SubElement(ide_evento, 'perApur').text = f'{year}-{month:02d}'
    ET.SubElement(ide_evento, 'tpAmb').text = '2'
    ET.SubElement(ide_evento, 'procEmi').text = '1'
    ET.SubElement(ide_evento, 'verProc').text = '1.0'

    ide_contrib = ET.SubElement(evt, 'ideContrib')
    ET.SubElement(ide_contrib, 'tpInsc').text = '1'
    ET.SubElement(ide_contrib, 'nrInsc').text = cnpj

    ide_pj = ET.SubElement(evt, 'idePJ')
    ET.SubElement(ide_pj, 'cnpjPrestador').text = cnpj

    natureza_map: dict = defaultdict(list)
    for ret in retencoes:
        nat = ret.codigo.natureza_rendimento or 'Não informado'
        natureza_map[nat].append(ret)

    for natureza, rets in natureza_map.items():
        det_pag = ET.SubElement(ide_pj, 'detPag')
        ET.SubElement(det_pag, 'natRend').text = str(natureza)
        total_base = sum((r.rendimento_tributavel or 0) for r in rets)
        total_retido = sum((r.valor or 0) for r in rets)
        ET.SubElement(det_pag, 'vrBaseRet').text = str(total_base)
        ET.SubElement(det_pag, 'vrRet').text = str(total_retido)

    raw = ET.tostring(root, encoding='unicode')
    return xml.dom.minidom.parseString(raw).toprettyxml(indent='  ')


def gerar_lotes_reinf(month: int, year: int) -> dict:
    """
    Generate EFD-Reinf XML batch files (lotes) for a given month/year.

    Business rules:
    - Requires a DadosContribuinte record; uses the first record returned by
      the database (the system is designed to hold a single configuration row).
      Raises ValueError if no record is configured.
    - Only includes RetencaoImposto records whose competência matches the
      given month/year AND whose associated DocumentoFiscal is atestada.
    - INSS retentions (CodigosImposto.familia == 'INSS') → R-2010 events.
    - Federal retentions (CodigosImposto.familia == 'FEDERAL') → R-4020 events.
    - One XML file is produced per unique provider CNPJ within each family.

    Returns:
        dict mapping filename (str) → XML content (str), including:
        - 'R-1000_Cadastro_Empresa.xml'
        - 'INSS_R2010/R2010_CNPJ_{cnpj}_{yyyymm}.xml' (one per INSS provider)
        - 'INSS_R2010/R2099_Fechamento.xml'
        - 'Federais_R4020/R4020_CNPJ_{cnpj}_{yyyymm}.xml' (one per Federal provider)
        - 'Federais_R4020/R4099_Fechamento.xml'
    """
    contribuinte = DadosContribuinte.objects.first()
    if contribuinte is None:
        raise ValueError("Dados do contribuinte não configurados.")

    cnpj_contribuinte = contribuinte.cnpj
    competencia = _build_competencia_date(month, year)

    retencoes = (
        RetencaoImposto.objects
        .filter(competencia=competencia, nota_fiscal__atestada=True)
        .select_related(
            'nota_fiscal',
            'nota_fiscal__nome_emitente',
            'codigo',
        )
    )

    inss_por_cnpj: dict = defaultdict(list)
    federal_por_cnpj: dict = defaultdict(list)

    for ret in retencoes:
        emitente = ret.nota_fiscal.nome_emitente
        if not emitente or not emitente.cpf_cnpj:
            continue
        provider_cnpj = emitente.cpf_cnpj
        if ret.codigo.familia == 'INSS':
            inss_por_cnpj[provider_cnpj].append(ret)
        elif ret.codigo.familia == 'FEDERAL':
            federal_por_cnpj[provider_cnpj].append(ret)

    # True when at least one retention was processed for the given category;
    # propagated to closing events (R-2099 / R-4099) to indicate movement.
    has_inss_movement = bool(inss_por_cnpj)
    has_federal_movement = bool(federal_por_cnpj)

    xmls: dict = {}

    xmls['R-1000_Cadastro_Empresa.xml'] = _build_r1000_xml(contribuinte)

    for provider_cnpj, rets in inss_por_cnpj.items():
        filename = f'INSS_R2010/R2010_CNPJ_{provider_cnpj}_{year}{month:02d}.xml'
        xmls[filename] = _build_r2010_xml(provider_cnpj, rets, month, year)

    for provider_cnpj, rets in federal_por_cnpj.items():
        filename = f'Federais_R4020/R4020_CNPJ_{provider_cnpj}_{year}{month:02d}.xml'
        xmls[filename] = _build_r4020_xml(provider_cnpj, rets, month, year)

    xmls['INSS_R2010/R2099_Fechamento.xml'] = _build_r2099_xml(
        cnpj_contribuinte, month, year, has_inss_movement,
    )
    xmls['Federais_R4020/R4099_Fechamento.xml'] = _build_r4099_xml(
        cnpj_contribuinte, month, year, has_federal_movement,
    )

    return xmls


def _build_r1000_xml(contribuinte: DadosContribuinte) -> str:
    """
    Build a skeleton R-1000 (evtInfoContri – Starter event) XML for the
    given taxpayer (DadosContribuinte instance).

    Returns a pretty-printed XML string.
    """
    root = ET.Element(
        'Reinf',
        xmlns='http://www.reinf.esocial.gov.br/schemas/evtInfoContribuinte/v2_01_01',
    )

    evt = ET.SubElement(root, 'evtInfoContri')

    ide_evento = ET.SubElement(evt, 'ideEvento')
    ET.SubElement(ide_evento, 'indRetif').text = '1'
    ET.SubElement(ide_evento, 'tpAmb').text = '2'
    ET.SubElement(ide_evento, 'procEmi').text = '1'
    ET.SubElement(ide_evento, 'verProc').text = '1.0'

    ide_contrib = ET.SubElement(evt, 'ideContrib')
    ET.SubElement(ide_contrib, 'tpInsc').text = str(contribuinte.tipo_inscricao)
    ET.SubElement(ide_contrib, 'nrInsc').text = contribuinte.cnpj

    info_contrib = ET.SubElement(evt, 'infoContrib')
    ET.SubElement(info_contrib, 'nmRazao').text = contribuinte.razao_social

    raw = ET.tostring(root, encoding='unicode')
    return xml.dom.minidom.parseString(raw).toprettyxml(indent='  ')


def _build_r2099_xml(cnpj_contribuinte: str, month: int, year: int, has_movement: bool = True) -> str:
    """
    Build a skeleton R-2099 (evtFechaEvPer – INSS closing event) XML.

    Returns a pretty-printed XML string.
    """
    root = ET.Element(
        'Reinf',
        xmlns='http://www.reinf.esocial.gov.br/schemas/evtFechaEvPer/v2_01_01',
    )

    evt = ET.SubElement(root, 'evtFechaEvPer')

    ide_evento = ET.SubElement(evt, 'ideEvento')
    ET.SubElement(ide_evento, 'indRetif').text = '1'
    ET.SubElement(ide_evento, 'perApur').text = f'{year}-{month:02d}'
    ET.SubElement(ide_evento, 'tpAmb').text = '2'
    ET.SubElement(ide_evento, 'procEmi').text = '1'
    ET.SubElement(ide_evento, 'verProc').text = '1.0'

    ide_contrib = ET.SubElement(evt, 'ideContrib')
    ET.SubElement(ide_contrib, 'tpInsc').text = '1'
    ET.SubElement(ide_contrib, 'nrInsc').text = cnpj_contribuinte

    fecha_ev_per = ET.SubElement(evt, 'fechaEvPer')
    ET.SubElement(fecha_ev_per, 'evtServTom').text = 'S' if has_movement else 'N'

    raw = ET.tostring(root, encoding='unicode')
    return xml.dom.minidom.parseString(raw).toprettyxml(indent='  ')


def _build_r4099_xml(cnpj_contribuinte: str, month: int, year: int, has_movement: bool = True) -> str:
    """
    Build a skeleton R-4099 (evtFechaEvPer – Federal taxes closing event) XML.

    Returns a pretty-printed XML string.
    """
    root = ET.Element(
        'Reinf',
        xmlns='http://www.reinf.esocial.gov.br/schemas/evtFechaEvPerFed/v2_01_01',
    )

    evt = ET.SubElement(root, 'evtFechaEvPer')

    ide_evento = ET.SubElement(evt, 'ideEvento')
    ET.SubElement(ide_evento, 'indRetif').text = '1'
    ET.SubElement(ide_evento, 'perApur').text = f'{year}-{month:02d}'
    ET.SubElement(ide_evento, 'tpAmb').text = '2'
    ET.SubElement(ide_evento, 'procEmi').text = '1'
    ET.SubElement(ide_evento, 'verProc').text = '1.0'

    ide_contrib = ET.SubElement(evt, 'ideContrib')
    ET.SubElement(ide_contrib, 'tpInsc').text = '1'
    ET.SubElement(ide_contrib, 'nrInsc').text = cnpj_contribuinte

    fecha_ev_per = ET.SubElement(evt, 'fechaEvPer')
    ET.SubElement(fecha_ev_per, 'evtRetPJ').text = 'S' if has_movement else 'N'

    raw = ET.tostring(root, encoding='unicode')
    return xml.dom.minidom.parseString(raw).toprettyxml(indent='  ')
