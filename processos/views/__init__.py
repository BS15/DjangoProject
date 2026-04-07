"""Agregador de pacotes de views. Preferir imports específicos de submodulos.

Exemplos de uso recomendado:
  from processos.views import cadastros as cadastro_views
  from processos.views import verbas as verbas_views
  from processos.views.fluxo.payment import panels as payment_panels

Evitar importações do agregador para melhor clareza de dependências.
"""

# Legacy reexports para compatibilidade transitória
from . import assinaturas
from . import cadastros
from . import chaos
from . import contas
from . import desenvolvedor
from . import fiscal
from . import fluxo
from . import relatorios
from . import suprimentos
from . import teste_pdf
from . import verbas
from .verbas import (
  add_auxilio_view,
  add_diaria_view,
  add_jeton_view,
  add_reembolso_view,
  agrupar_verbas_view,
  auxilios_list_view,
  diarias_list_view,
  edit_auxilio_view,
  edit_jeton_view,
  edit_reembolso_view,
  jetons_list_view,
  reembolsos_list_view,
)
from ..validators import STATUS_BLOQUEADOS_TOTAL, STATUS_SOMENTE_DOCUMENTOS

__all__ = [
    'assinaturas',
    'cadastros',
    'chaos',
    'contas',
    'desenvolvedor',
    'fiscal',
    'fluxo',
    'relatorios',
    'suprimentos',
    'teste_pdf',
    'verbas',
    'add_auxilio_view',
    'add_diaria_view',
    'add_jeton_view',
    'add_reembolso_view',
    'agrupar_verbas_view',
    'auxilios_list_view',
    'diarias_list_view',
    'edit_auxilio_view',
    'edit_jeton_view',
    'edit_reembolso_view',
    'jetons_list_view',
    'reembolsos_list_view',
    'STATUS_BLOQUEADOS_TOTAL',
    'STATUS_SOMENTE_DOCUMENTOS',
]
