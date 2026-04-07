"""Facade de compatibilidade para paineis do fluxo de pagamento."""

from .autorizacao.panels import *
from .contas_a_pagar.panels import *
from .lancamento.panels import *


__all__ = ["STATUSES_CONTAS_A_PAGAR", "lancamento_bancario", "contas_a_pagar", "painel_autorizacao_view"]