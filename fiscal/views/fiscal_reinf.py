"""Compatibilidade de imports para views EFD-Reinf."""

from .reinf.actions import gerar_lote_reinf_legacy_action
from .reinf.panels import painel_reinf_view

__all__ = ["painel_reinf_view", "gerar_lote_reinf_legacy_action"]
