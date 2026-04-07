"""Views do fluxo de pagamento organizadas por funcao operacional.

Este pacote preserva a interface publica historica de
`processos.views.fluxo.payment`, mas separa endpoints de leitura
(painéis/listagens) dos endpoints de acao/mutacao.
"""

from .actions import *
from .autorizacao import *
from .comprovantes import *
from .contas_a_pagar import *
from .lancamento import *
from .panels import *

__all__ = [
    "separar_para_lancamento_bancario",
    "lancamento_bancario",
    "marcar_como_lancado",
    "desmarcar_lancamento",
    "contas_a_pagar",
    "enviar_para_autorizacao",
    "painel_autorizacao_view",
    "autorizar_pagamento",
    "recusar_autorizacao_view",
    "painel_comprovantes_view",
    "api_fatiar_comprovantes",
    "api_vincular_comprovantes",
]