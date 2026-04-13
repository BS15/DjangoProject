"""Serviços de agregação e geração XML para painel EFD-Reinf."""

import xml.dom.minidom
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date

from fiscal.models import RetencaoImposto
from fiscal.models import DadosContribuinte


def _build_competencia_date(month: int, year: int) -> date:
    return date(year, month, 1)


def get_serie_2000_data(month: int | None, year: int | None) -> list:
    qs = RetencaoImposto.objects.filter(codigo__serie_reinf='S2000')
    if month is not None and year is not None:
        qs = qs.filter(competencia=_build_competencia_date(month, year))

    retencoes = qs.select_related(
        'nota_fiscal',
        'nota_fiscal__nome_emitente',
        'codigo',
        'beneficiario',
    ).order_by(
        'nota_fiscal__nome_emitente__nome',
        'nota_fiscal__data_emissao',
        'nota_fiscal__id',
    )

    credor_map: dict = defaultdict(lambda: defaultdict(list))
    for retencao in retencoes:
        credor_map[retencao.nota_fiscal.nome_emitente][retencao.nota_fiscal].append(retencao)

    result = []
    for credor, nf_map in credor_map.items():
        credor_total_retido = 0
        notas = []
        for nota_fiscal, rets in nf_map.items():
            total_bruto = nota_fiscal.valor_bruto or 0
            total_base = sum((ret.rendimento_tributavel or 0) for ret in rets)
            total_retido = sum((ret.valor or 0) for ret in rets)
            credor_total_retido += total_retido
            notas.append({
                'nota_fiscal': nota_fiscal,
                'retencoes': rets,
                'total_bruto': total_bruto,
                'total_base': total_base,
                'total_retido': total_retido,
            })
        result.append({'credor': credor, 'notas': notas, 'total_retido': credor_total_retido})

    return result


def get_serie_4000_data(month: int | None, year: int | None) -> list:
    qs = RetencaoImposto.objects.filter(codigo__serie_reinf='S4000')
    if month is not None and year is not None:
        qs = qs.filter(competencia=_build_competencia_date(month, year))

    retencoes = qs.select_related(
        'nota_fiscal',
        'nota_fiscal__nome_emitente',
        'beneficiario',
        'codigo',
    ).order_by(
        'beneficiario__nome',
        'codigo__natureza_rendimento',
        'competencia',
    )

    beneficiario_map: dict = defaultdict(lambda: defaultdict(list))
    for retencao in retencoes:
        natureza = retencao.codigo.natureza_rendimento or 'Não informado'
        beneficiario_map[retencao.beneficiario][natureza].append(retencao)

    result = []
    for beneficiario, natureza_map in beneficiario_map.items():
        beneficiario_total_retido = 0
        naturezas = []
        for natureza, rets in natureza_map.items():
            total_bruto = sum((ret.rendimento_tributavel or 0) for ret in rets)
            total_retido = sum((ret.valor or 0) for ret in rets)
            beneficiario_total_retido += total_retido
            naturezas.append({
                'natureza_codigo': natureza,
                'retencoes': rets,
                'total_bruto': total_bruto,
                'total_retido': total_retido,
            })
        evento = 'R-4010' if (beneficiario and beneficiario.tipo == 'PF') else 'R-4020'
        result.append({
            'beneficiario': beneficiario,
            'evento': evento,
            'naturezas': naturezas,
            'total_retido': beneficiario_total_retido,
        })

    return result


def _build_r2010_xml(cnpj: str, retencoes: list, month: int, year: int) -> str:
    root = ET.Element('Reinf', xmlns='http://www.reinf.esocial.gov.br/schemas/evtServTom/v2_01_01')
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
    for retencao in retencoes:
        nota_fiscal = retencao.nota_fiscal
        nf_seq = ET.SubElement(det_evt, 'nfSeq')
        ET.SubElement(nf_seq, 'nrNF').text = str(nota_fiscal.numero_nota_fiscal or '')
        ET.SubElement(nf_seq, 'dtEmiNF').text = str(nota_fiscal.data_emissao)
        ET.SubElement(nf_seq, 'vrBruto').text = str(nota_fiscal.valor_bruto or 0)

        det_ret = ET.SubElement(nf_seq, 'detRet')
        ET.SubElement(det_ret, 'vrBaseRet').text = str(retencao.rendimento_tributavel or 0)
        ET.SubElement(det_ret, 'vrRet').text = str(retencao.valor or 0)

    raw = ET.tostring(root, encoding='unicode')
    return xml.dom.minidom.parseString(raw).toprettyxml(indent='  ')


def _build_r4020_xml(cnpj: str, retencoes: list, month: int, year: int) -> str:
    root = ET.Element('Reinf', xmlns='http://www.reinf.esocial.gov.br/schemas/evtRetPJ/v2_01_01')
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
    for retencao in retencoes:
        natureza_map[retencao.codigo.natureza_rendimento or 'Não informado'].append(retencao)

    for natureza, rets in natureza_map.items():
        det_pag = ET.SubElement(ide_pj, 'detPag')
        ET.SubElement(det_pag, 'natRend').text = str(natureza)
        ET.SubElement(det_pag, 'vrBaseRet').text = str(sum((ret.rendimento_tributavel or 0) for ret in rets))
        ET.SubElement(det_pag, 'vrRet').text = str(sum((ret.valor or 0) for ret in rets))

    raw = ET.tostring(root, encoding='unicode')
    return xml.dom.minidom.parseString(raw).toprettyxml(indent='  ')


def _build_r1000_xml(contribuinte) -> str:
    root = ET.Element('Reinf')
    evt = ET.SubElement(root, 'evtInfoContri')
    ide_contrib = ET.SubElement(evt, 'ideContri')
    ET.SubElement(ide_contrib, 'tpInsc').text = str(contribuinte.tipo_inscricao or 1)
    ET.SubElement(ide_contrib, 'nrInsc').text = str(contribuinte.cnpj)
    ET.SubElement(ide_contrib, 'nmRazao').text = str(contribuinte.razao_social or '')
    raw = ET.tostring(root, encoding='unicode')
    return xml.dom.minidom.parseString(raw).toprettyxml(indent='  ')


def _build_fechamento_xml(evento: str, per_apur: str) -> str:
    root = ET.Element('Reinf')
    evt = ET.SubElement(root, evento)
    ide_evento = ET.SubElement(evt, 'ideEvento')
    ET.SubElement(ide_evento, 'perApur').text = per_apur
    raw = ET.tostring(root, encoding='unicode')
    return xml.dom.minidom.parseString(raw).toprettyxml(indent='  ')


def gerar_lotes_reinf(month: int, year: int) -> dict:
    contribuinte = DadosContribuinte.objects.first()
    if contribuinte is None:
        raise ValueError('Dados do contribuinte não configurados.')

    retencoes = RetencaoImposto.objects.filter(
        competencia=_build_competencia_date(month, year),
        nota_fiscal__atestada=True,
    ).select_related('nota_fiscal', 'nota_fiscal__nome_emitente', 'codigo')

    inss_por_cnpj: dict = defaultdict(list)
    federal_por_cnpj: dict = defaultdict(list)
    for retencao in retencoes:
        emitente = retencao.nota_fiscal.nome_emitente
        if not emitente or not emitente.cpf_cnpj:
            continue
        if retencao.codigo.serie_reinf == 'S2000':
            inss_por_cnpj[emitente.cpf_cnpj].append(retencao)
        elif retencao.codigo.serie_reinf == 'S4000':
            federal_por_cnpj[emitente.cpf_cnpj].append(retencao)

    per_apur = f'{year}-{month:02d}'
    xmls = {
        'R-1000_Cadastro_Empresa.xml': _build_r1000_xml(contribuinte),
        'INSS_R2010/R2099_Fechamento.xml': _build_fechamento_xml('evtFechaEvPer', per_apur),
        'Federais_R4020/R4099_Fechamento.xml': _build_fechamento_xml('evtFechaEvPer', per_apur),
    }
    cnpj_contribuinte = contribuinte.cnpj
    for provider_cnpj, rets in inss_por_cnpj.items():
        xmls[f'INSS_R2010/R2010_CNPJ_{provider_cnpj}_{year}{month:02d}.xml'] = _build_r2010_xml(
            cnpj_contribuinte,
            rets,
            month,
            year,
        )
    for provider_cnpj, rets in federal_por_cnpj.items():
        xmls[f'Federais_R4020/R4020_CNPJ_{provider_cnpj}_{year}{month:02d}.xml'] = _build_r4020_xml(
            cnpj_contribuinte,
            rets,
            month,
            year,
        )

    return xmls


__all__ = [
    '_build_r2010_xml',
    '_build_r4020_xml',
    'gerar_lotes_reinf',
    'get_serie_2000_data',
    'get_serie_4000_data',
]