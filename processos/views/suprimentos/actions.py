"""Facade de compatibilidade para acoes do fluxo de suprimentos."""

from .prestacao_contas.actions import *


__all__ = ["adicionar_despesa_action", "fechar_suprimento_action"]
