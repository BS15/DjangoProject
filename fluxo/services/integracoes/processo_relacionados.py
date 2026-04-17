"""Orquestra integrações entre Processo e domínios modulares vinculados."""

from django.utils.module_loading import import_string


GERADORES_POR_TRANSICAO = (
    "suprimentos.services.processo_integration.gerar_documentos_relacionados_por_transicao",
    "verbas_indenizatorias.services.processo_integration.gerar_documentos_relacionados_por_transicao",
)

SINCRONIZADORES_POR_TRANSICAO = (
    "suprimentos.services.processo_integration.sincronizar_relacoes_apos_transicao",
    "verbas_indenizatorias.services.processo_integration.sincronizar_relacoes_apos_transicao",
)


def gerar_documentos_relacionados_por_transicao(processo, status_anterior, novo_status):
    """Delegates generation of domain-specific documents to each linked app."""
    for dotted_path in GERADORES_POR_TRANSICAO:
        import_string(dotted_path)(processo, status_anterior, novo_status)


def sincronizar_relacoes_apos_transicao(processo, status_anterior, novo_status, usuario=None):
    """Propaga efeitos de transição do processo para domínios vinculados."""
    for dotted_path in SINCRONIZADORES_POR_TRANSICAO:
        import_string(dotted_path)(processo, status_anterior, novo_status, usuario=usuario)
