"""Helpers do fluxo financeiro — re-exporta API pública dos submódulos.

Organização por responsabilidade:
- audit_builders.py: builders de payloads de auditoria e histórico
- queries.py: utilitários genéricos de query e ordenação
- payment_builders.py: builders de dados para painéis de pagamento e ações em lote
- workflows.py: filas de revisão, aprovação/recusa e formulários de fluxo
"""
from .queries import (
    _obter_campo_ordenacao,
    _resolver_parametros_ordenacao,
    _aplicar_filtro_por_opcao,
)
from .audit_builders import (
    _aplicar_filtros_historico,
    _serializar_documentos_processo_auditoria,
    _serializar_pendencias_processo_auditoria,
    _serializar_retencoes_processo_auditoria,
    _serializar_processo_base,
    _build_payload_documentos_processo_auditoria,
    _build_payload_processo_detalhes,
    _build_history_record,
    _get_unified_history,
)
from .payment_builders import (
    _obter_estatisticas_boletos,
    _gerar_agrupamentos_contas_a_pagar,
    _aplicar_filtros_contas_a_pagar,
    _build_detalhes_pagamento,
    _consolidar_totais_pagamento,
    _processar_acao_lote,
)
from .errors import ArquivamentoDefinitivoError, ArquivamentoSemDocumentosError
from .workflows import (
    _iniciar_fila_sessao,
    _handle_queue_navigation,
    _processo_fila_detalhe_view,
    _aprovar_processo_view,
    _recusar_processo_view,
)

__all__ = [
    # queries
    "_obter_campo_ordenacao",
    "_resolver_parametros_ordenacao",
    "_aplicar_filtro_por_opcao",
    # audit_builders
    "_aplicar_filtros_historico",
    "_build_history_record",
    "_build_payload_documentos_processo_auditoria",
    "_build_payload_processo_detalhes",
    "_get_unified_history",
    # payment_builders
    "_obter_estatisticas_boletos",
    "_gerar_agrupamentos_contas_a_pagar",
    "_aplicar_filtros_contas_a_pagar",
    "_build_detalhes_pagamento",
    "_consolidar_totais_pagamento",
    "_processar_acao_lote",
    # errors
    "ArquivamentoDefinitivoError",
    "ArquivamentoSemDocumentosError",
    # workflows
    "_iniciar_fila_sessao",
    "_handle_queue_navigation",
    "_processo_fila_detalhe_view",
    "_aprovar_processo_view",
    "_recusar_processo_view",
]
