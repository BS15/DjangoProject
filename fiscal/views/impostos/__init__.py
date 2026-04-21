"""Tax retention management views."""

from .panels import painel_impostos_view, registrar_documentos_pagamento_view
from .actions import (
    agrupar_retencoes_action,
    anexar_documentos_retencoes_action,
    selecionar_retencoes_documentacao_action,
    remover_retencao_documentacao_action,
    registrar_documentos_pagamento_action,
)
from .apis import api_processar_retencoes

__all__ = [
    "painel_impostos_view",
    "registrar_documentos_pagamento_view",
    "agrupar_retencoes_action",
    "anexar_documentos_retencoes_action",
    "selecionar_retencoes_documentacao_action",
    "remover_retencao_documentacao_action",
    "registrar_documentos_pagamento_action",
    "api_processar_retencoes",
]
