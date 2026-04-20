"""Registry e utilitarios de configuracao por tipo de verba."""

from credores.models import Credor
from pagamentos.domain_models import TiposDocumento
from verbas_indenizatorias.models import (
    AuxilioRepresentacao,
    Diaria,
    DocumentoAuxilio,
    DocumentoComprovacao,
    DocumentoDiaria,
    DocumentoJeton,
    DocumentoReembolso,
    Jeton,
    ReembolsoCombustivel,
)

_CREDOR_AGRUPAMENTO_MULTIPLO = "BANCO DO BRASIL S/A"

_VERBA_CONFIG = {
    "diaria": {
        "model": Diaria,
        "list_url": "diarias_list",
        "doc_model": DocumentoDiaria,
        "doc_fk": "diaria",
        "doc_tipo_seguro": "verba_diaria_doc",
    },
    "diaria_comprovante": {
        "model": Diaria,
        "list_url": "diarias_list",
        "doc_model": DocumentoComprovacao,
        "doc_fk": "prestacao",
        "doc_tipo_seguro": "verba_diaria_comprov",
    },
    "reembolso": {
        "model": ReembolsoCombustivel,
        "list_url": "reembolsos_list",
        "doc_model": DocumentoReembolso,
        "doc_fk": "reembolso",
        "doc_tipo_seguro": "verba_reembolso_doc",
    },
    "jeton": {
        "model": Jeton,
        "list_url": "jetons_list",
        "doc_model": DocumentoJeton,
        "doc_fk": "jeton",
        "doc_tipo_seguro": "verba_jeton_doc",
    },
    "auxilio": {
        "model": AuxilioRepresentacao,
        "list_url": "auxilios_list",
        "doc_model": DocumentoAuxilio,
        "doc_fk": "auxilio",
        "doc_tipo_seguro": "verba_auxilio_doc",
    },
}

_VERBA_PERMISSION_MAP = {
    "diaria": "verbas_indenizatorias.pode_gerenciar_diarias",
    "diaria_comprovante": "verbas_indenizatorias.pode_gerenciar_diarias",
    "reembolso": "verbas_indenizatorias.pode_gerenciar_reembolsos",
    "jeton": "verbas_indenizatorias.pode_gerenciar_jetons",
    "auxilio": "verbas_indenizatorias.pode_gerenciar_auxilios",
}


def _get_tipos_documento_ativos():
    """Retorna os tipos de documento ativos disponíveis para anexação."""
    return TiposDocumento.objects.filter(ativo=True)


def _get_tipos_documento_verbas():
    """Retorna apenas os tipos de documento ativos vinculados a VERBAS INDENIZATÓRIAS."""
    return TiposDocumento.objects.filter(
        ativo=True,
        tipo_pagamento__tipo_pagamento__iexact="VERBAS INDENIZATÓRIAS",
    )


def _get_permissao_gestao_verba(tipo_verba):
    """Resolve a permissão Django necessária para gerenciar o tipo de verba."""
    return _VERBA_PERMISSION_MAP.get(tipo_verba)


def _obter_credor_agrupamento(itens):
    """Obtém o credor de agrupamento para lote, criando credor padrão quando necessário."""
    beneficiario_ids = {item.beneficiario_id for item in itens if item.beneficiario_id}
    if len(beneficiario_ids) <= 1:
        return next((item.beneficiario for item in itens if item.beneficiario_id), None)

    credor_banco, _ = Credor.objects.get_or_create(
        nome__iexact=_CREDOR_AGRUPAMENTO_MULTIPLO,
        defaults={"nome": _CREDOR_AGRUPAMENTO_MULTIPLO, "tipo": "PJ"},
    )
    return credor_banco
