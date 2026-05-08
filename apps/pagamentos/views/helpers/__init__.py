"""Helpers do fluxo financeiro — re-exporta API pública dos submódulos.

Organização por responsabilidade:
- audit_builders.py: builders de payloads de auditoria e histórico
- payment_builders.py: builders de dados para painéis de pagamento e ações em lote
- workflows.py: filas de revisão, aprovação/recusa e formulários de fluxo
"""
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
    _atualizar_status_em_lote,
    _processar_acao_lote,
)
from .errors import ArquivamentoDefinitivoError, ArquivamentoSemDocumentosError
from .contingencias import (
    determinar_requisitos_contingencia,
    normalizar_dados_propostos_contingencia,
    sincronizar_flag_contingencia_processo,
    processar_aprovacao_contingencia,
    processar_revisao_contadora_contingencia,
)
from .workflows import (
    _iniciar_fila_sessao,
    _handle_queue_navigation,
    _processo_fila_detalhe_view,
    _aprovar_processo_view,
    _recusar_processo_view,
)

__all__ = [
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
    "_atualizar_status_em_lote",
    "_processar_acao_lote",
    # errors
    "ArquivamentoDefinitivoError",
    "ArquivamentoSemDocumentosError",
    # contingencias
    "determinar_requisitos_contingencia",
    "normalizar_dados_propostos_contingencia",
    "sincronizar_flag_contingencia_processo",
    "processar_aprovacao_contingencia",
    "processar_revisao_contadora_contingencia",
    # workflows
    "_iniciar_fila_sessao",
    "_handle_queue_navigation",
    "_processo_fila_detalhe_view",
    "_aprovar_processo_view",
    "_recusar_processo_view",
]
