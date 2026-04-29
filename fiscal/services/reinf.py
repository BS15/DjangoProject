"""Serviços de agregação e geração XML para painel EFD-Reinf."""

import xml.dom.minidom
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import re

from fiscal.models import RetencaoImposto
from fiscal.models import DadosContribuinte


def _build_competencia_date(month: int, year: int) -> date:
    """Constrói objeto date de competência no primeiro dia do mês."""
    return date(year, month, 1)


def _fmt_dec(value) -> str:
    """Formata valores decimais no padrão XML fiscal com 2 casas."""
    return f"{Decimal(value or 0).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def _digits_only(value: str | None) -> str:
    """Retorna apenas os dígitos numéricos da string."""
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _natureza_rendimento_valida(natureza: str | None) -> bool:
    """Verifica se a natureza do rendimento é válida (5 dígitos)."""
    return bool(re.fullmatch(r"\d{5}", str(natureza or "")))


def get_serie_2000_data(month: int | None, year: int | None) -> list:
    """Retorna dados agregados por credor/NF para eventos S2000 (INSS) da competência."""
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
    """Retorna dados agregados por beneficiário/natureza para eventos S4000 (IR/CSRF) da competência."""
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
    """Gera XML do evento R-2010 (serviços tomados com retenção INSS) para a competência."""
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
        ET.SubElement(nf_seq, 'vrBruto').text = _fmt_dec(nota_fiscal.valor_bruto)

        det_ret = ET.SubElement(nf_seq, 'detRet')
        ET.SubElement(det_ret, 'vrBaseRet').text = _fmt_dec(retencao.rendimento_tributavel)
        ET.SubElement(det_ret, 'vrRet').text = _fmt_dec(retencao.valor)

    raw = ET.tostring(root, encoding='unicode')
    return xml.dom.minidom.parseString(raw).toprettyxml(indent='  ')


def _build_r4020_xml(cnpj: str, items: list, month: int, year: int) -> str:
    """Gera XML do evento R-4020 (pagamentos a PJ com retenção CSRF ou isentos).
    
    Args:
        cnpj: CNPJ do prestador/tomador
        items: Lista mista de RetencaoImposto e DocumentoFiscal (isentas)
        month: Mês da competência
        year: Ano da competência
    """
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

    # Agrupa por natureza de rendimento
    det_pag_map: dict = defaultdict(lambda: {'vlrRet': 0, 'vlrBaseRet': 0, 'vlrIsento': 0, 'tpIsencao': None, 'descIsencao': None})
    
    for item in items:
        # Trata RetencaoImposto
        if hasattr(item, 'codigo') and hasattr(item, 'rendimento_tributavel'):  # É RetencaoImposto
            natureza = item.codigo.natureza_rendimento or 'Não informado'
            det_pag_map[natureza]['vlrBaseRet'] += (item.rendimento_tributavel or 0)
            det_pag_map[natureza]['vlrRet'] += (item.valor or 0)
            det_pag_map[natureza]['natRend'] = natureza
        
        # Trata DocumentoFiscal isenta
        elif hasattr(item, 'is_rendimento_isento') and item.is_rendimento_isento:  # É DocumentoFiscal
            # Para notas isentas, usamos a natureza padrão ou informada
            natureza = '15001'  # Natureza padrão para serviços
            det_pag_map[natureza]['vlrIsento'] += (item.valor_bruto or 0)
            det_pag_map[natureza]['tpIsencao'] = item.tpIsencao or '99'
            det_pag_map[natureza]['descIsencao'] = item.descIsencao or ''
            det_pag_map[natureza]['natRend'] = natureza

    # Monta XML detPag
    for det in det_pag_map.values():
        det_pag = ET.SubElement(ide_pj, 'detPag')
        ET.SubElement(det_pag, 'natRend').text = str(det.get('natRend', ''))
        
        # Valor retido (caso tenha retenção)
        vlr_ret = det.get('vlrRet', 0)
        vlr_base = det.get('vlrBaseRet', 0)
        if vlr_ret and vlr_ret > 0:
            ET.SubElement(det_pag, 'vrBaseRet').text = _fmt_dec(vlr_base)
            ET.SubElement(det_pag, 'vrRet').text = _fmt_dec(vlr_ret)
        
        # Valor isento (caso seja entidade imune/isenta)
        vlr_isento = det.get('vlrIsento', 0)
        if vlr_isento and vlr_isento > 0:
            rend_isento = ET.SubElement(det_pag, 'rendIsento')
            ET.SubElement(rend_isento, 'vlrIsento').text = _fmt_dec(vlr_isento)
            
            tp_isencao = det.get('tpIsencao')
            if tp_isencao:
                ET.SubElement(rend_isento, 'tpIsencao').text = str(tp_isencao)
                
                desc_isencao = det.get('descIsencao')
                if desc_isencao and tp_isencao == '99':  # Campo obrigatório para código 99
                    ET.SubElement(rend_isento, 'descIsencao').text = str(desc_isencao)[:255]

    raw = ET.tostring(root, encoding='unicode')
    return xml.dom.minidom.parseString(raw).toprettyxml(indent='  ')


def _build_r1000_xml(contribuinte) -> str:
    """Gera XML do evento R-1000 com identificação do contribuinte."""
    root = ET.Element('Reinf')
    evt = ET.SubElement(root, 'evtInfoContri')
    ide_contrib = ET.SubElement(evt, 'ideContri')
    ET.SubElement(ide_contrib, 'tpInsc').text = str(contribuinte.tipo_inscricao or 1)
    ET.SubElement(ide_contrib, 'nrInsc').text = _digits_only(contribuinte.cnpj)
    ET.SubElement(ide_contrib, 'nmRazao').text = str(contribuinte.razao_social or '')
    raw = ET.tostring(root, encoding='unicode')
    return xml.dom.minidom.parseString(raw).toprettyxml(indent='  ')


def _build_fechamento_xml(evento: str, per_apur: str) -> str:
    """Gera XML de evento de fechamento de período para EFD-Reinf."""
    root = ET.Element('Reinf')
    evt = ET.SubElement(root, evento)
    ide_evento = ET.SubElement(evt, 'ideEvento')
    ET.SubElement(ide_evento, 'perApur').text = per_apur
    raw = ET.tostring(root, encoding='unicode')
    return xml.dom.minidom.parseString(raw).toprettyxml(indent='  ')


def gerar_lotes_reinf(month: int, year: int) -> dict:
    """Gera todos os lotes XML da EFD-Reinf para a competência, agrupados por série.
    
    Inclui:
    - Retenções normais (IR/CSRF/PIS/COFINS)
    - Pagamentos a entidades imunes/isentas (sem retenção)
    """
    from fiscal.models import DocumentoFiscal
    
    contribuinte = DadosContribuinte.objects.first()
    if contribuinte is None:
        raise ValueError('Dados do contribuinte não configurados.')

    retencoes = RetencaoImposto.objects.filter(
        competencia=_build_competencia_date(month, year),
        nota_fiscal__atestada=True,
    ).select_related('nota_fiscal', 'nota_fiscal__nome_emitente', 'codigo')

    inconsistencias = []
    for retencao in retencoes:
        emitente = retencao.nota_fiscal.nome_emitente if retencao.nota_fiscal else None
        cnpj_emitente = _digits_only(getattr(emitente, 'cpf_cnpj', None))
        if not emitente or not cnpj_emitente:
            inconsistencias.append(
                f"Retencao #{retencao.id} sem emitente válido para EFD-Reinf."
            )

        if retencao.codigo.serie_reinf == 'S4000':
            natureza = retencao.codigo.natureza_rendimento
            if not _natureza_rendimento_valida(natureza):
                inconsistencias.append(
                    f"Retencao #{retencao.id} com natureza_rendimento inválida ({natureza!r}) para série S4000."
                )

    if inconsistencias:
        raise ValueError("Inconsistências fiscais impedem geração Reinf: " + " | ".join(inconsistencias))

    inss_por_cnpj: dict = defaultdict(list)
    federal_por_cnpj: dict = defaultdict(list)
    for retencao in retencoes:
        emitente = retencao.nota_fiscal.nome_emitente
        provider_cnpj = _digits_only(emitente.cpf_cnpj)
        if retencao.codigo.serie_reinf == 'S2000':
            inss_por_cnpj[provider_cnpj].append(retencao)
        elif retencao.codigo.serie_reinf == 'S4000':
            federal_por_cnpj[provider_cnpj].append(retencao)

    # Busca também notas com rendimento isento/imune (sem retenção)
    notas_isentas = DocumentoFiscal.objects.filter(
        is_rendimento_isento=True,
        atestada=True,
        processo__data_pagamento__year=year,
        processo__data_pagamento__month=month,
    ).select_related('nome_emitente')
    
    # Agrupa notas isentas por emitente para incluir no XML federal
    for nota in notas_isentas:
        if nota.nome_emitente:
            provider_cnpj = _digits_only(nota.nome_emitente.cpf_cnpj)
            # Cria um "pseudo objeto" para representar a nota isenta na estrutura do XML
            federal_por_cnpj[provider_cnpj].append(nota)

    per_apur = f'{year}-{month:02d}'
    xmls = {
        'R-1000_Cadastro_Empresa.xml': _build_r1000_xml(contribuinte),
        'INSS_R2010/R2099_Fechamento.xml': _build_fechamento_xml('evtFechaEvPer', per_apur),
        'Federais_R4020/R4099_Fechamento.xml': _build_fechamento_xml('evtFechaEvPer', per_apur),
    }
    cnpj_contribuinte = _digits_only(contribuinte.cnpj)
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