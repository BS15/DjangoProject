"""Funcoes auxiliares para processos de contingencia."""

from typing import Tuple


def _usuario_pode_acessar_painel_contingencias(user) -> bool:
    """Verifica se usuario tem acesso ao painel de contingencias."""
    return any(
        user.has_perm(perm)
        for perm in (
            "fluxo.acesso_backoffice",
            "fluxo.pode_aprovar_contingencia_supervisor",
            "fluxo.pode_autorizar_pagamento",
            "fluxo.pode_auditar_conselho",
            "fluxo.pode_contabilizar",
        )
    )


def _validar_permissao_por_etapa(user, status_contingencia: str) -> bool:
    """Valida se usuario tem permissao para a etapa atual da contingencia."""
    if status_contingencia == "PENDENTE_SUPERVISOR":
        return user.has_perm("fluxo.pode_aprovar_contingencia_supervisor")
    if status_contingencia == "PENDENTE_ORDENADOR":
        return user.has_perm("fluxo.pode_autorizar_pagamento")
    if status_contingencia == "PENDENTE_CONSELHO":
        return user.has_perm("fluxo.pode_auditar_conselho")
    if status_contingencia == "PENDENTE_CONTADOR":
        return user.has_perm("fluxo.pode_contabilizar")
    return False


__all__ = [
    "_usuario_pode_acessar_painel_contingencias",
    "_validar_permissao_por_etapa",
]
