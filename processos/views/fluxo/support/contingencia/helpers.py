"""Funcoes auxiliares para processos de contingencia."""

from typing import Tuple


def _usuario_pode_acessar_painel_contingencias(user) -> bool:
    """Verifica se usuario tem acesso ao painel de contingencias."""
    return any(
        user.has_perm(perm)
        for perm in (
            "processos.acesso_backoffice",
            "processos.pode_aprovar_contingencia_supervisor",
            "processos.pode_autorizar_pagamento",
            "processos.pode_auditar_conselho",
            "processos.pode_contabilizar",
        )
    )


def _validar_permissao_por_etapa(user, status_contingencia: str) -> bool:
    """Valida se usuario tem permissao para a etapa atual da contingencia."""
    if status_contingencia == "PENDENTE_SUPERVISOR":
        return user.has_perm("processos.pode_aprovar_contingencia_supervisor")
    if status_contingencia == "PENDENTE_ORDENADOR":
        return user.has_perm("processos.pode_autorizar_pagamento")
    if status_contingencia == "PENDENTE_CONSELHO":
        return user.has_perm("processos.pode_auditar_conselho")
    if status_contingencia == "PENDENTE_CONTADOR":
        return user.has_perm("processos.pode_contabilizar")
    return False


__all__ = [
    "_usuario_pode_acessar_painel_contingencias",
    "_validar_permissao_por_etapa",
]
