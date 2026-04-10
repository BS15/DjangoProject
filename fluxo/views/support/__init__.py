"""Facade de views de suporte transversal: pendencias, contingencias e devolucoes.

Este modulo esta organizado segundo um modelo hibrido de responsabilidade:
- Cada centro de logica de negocio tem sua propria pasta (contingencia, devolucao, pendencia)
- Dentro de cada pasta, as views sao separadas por tipo de operacao:
  * panels.py: views GET (leitura, painneis, formularios)
  * actions.py: views POST (mutacoes, persistencias)

Mantemos compatibilidade com imports legados.
"""

# Core views (home_page, process_detail_view + helpers)
from .core import *

# Sync
from .sync import *

# Pendencia
from .pendencia import *

# Contingencia
from .contingencia import *

# Devolucao
from .devolucao import *

__all__ = [
    # Core
    "home_page",
    "process_detail_view",
    "_obter_campo_ordenacao",
    "sync_siscac_payments",
    "sincronizar_siscac",
    "sincronizar_siscac_manual_action",
    "sincronizar_siscac_auto_action",
    "aplicar_aprovacao_contingencia",
    "determinar_requisitos_contingencia",
    "normalizar_dados_propostos_contingencia",
    "proximo_status_contingencia",
    "sincronizar_flag_contingencia_processo",
    # Pendencia
    "painel_pendencias_view",
    # Contingencia
    "painel_contingencias_view",
    "add_contingencia_view",
    "add_contingencia_action",
    "analisar_contingencia_view",
    # Devolucao
    "painel_devolucoes_view",
    "registrar_devolucao_view",
    "registrar_devolucao_action",
]
