"""Orquestra integrações entre Processo e domínios modulares vinculados."""


def gerar_documentos_relacionados_por_transicao(processo, status_anterior, novo_status):
    """Delegates generation of domain-specific documents to each linked app."""
    from suprimentos.services.processo_integration import gerar_documentos_relacionados_por_transicao as gerar_suprimentos
    from verbas_indenizatorias.services.processo_integration import gerar_documentos_relacionados_por_transicao as gerar_verbas

    gerar_verbas(processo, status_anterior, novo_status)
    gerar_suprimentos(processo, status_anterior, novo_status)


def sincronizar_relacoes_apos_transicao(processo, status_anterior, novo_status, usuario=None):
    """Propaga efeitos de transição do processo para domínios vinculados."""
    from suprimentos.services.processo_integration import sincronizar_relacoes_apos_transicao as sincronizar_suprimentos
    from verbas_indenizatorias.services.processo_integration import sincronizar_relacoes_apos_transicao as sincronizar_verbas

    sincronizar_verbas(processo, status_anterior, novo_status, usuario=usuario)
    sincronizar_suprimentos(processo, status_anterior, novo_status, usuario=usuario)
