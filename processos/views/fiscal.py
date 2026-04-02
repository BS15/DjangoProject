"""
Agregador de compatibilidade para views fiscais.

As views fiscais foram refatoradas para módulos temáticos mantendo a interface pública compatível:
- fiscal_documentos.py: gerenciamento de documentos fiscais (Notas Fiscais)
- fiscal_liquidacoes.py: painel de liquidações e ateste
- fiscal_retencoes.py: painel de impostos e agrupamento
- fiscal_reinf.py: painel EFD-Reinf
- fiscal_comprovantes.py: painel de comprovantes pós-pagamento

Nota: Use imports diretos dos módulos temáticos para novo código.
"""

# Compatibilidade para imports legados
from .fiscal_comprovantes import *
from .fiscal_documentos import *
from .fiscal_liquidacoes import *
from .fiscal_reinf import *
from .fiscal_retencoes import *

