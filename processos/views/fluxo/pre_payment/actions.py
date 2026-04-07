"""Facade de compatibilidade para acoes de pre-pagamento."""

from .empenho.actions import *


__all__ = ["registrar_empenho_action", "avancar_para_pagamento_view"]
