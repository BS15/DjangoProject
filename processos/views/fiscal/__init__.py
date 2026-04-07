"""
Agregador de compatibilidade para views fiscais.

Os módulos fiscal_retencoes e fiscal_reinf permanecem neste pacote.
Os demais foram movidos para os módulos de fluxo canônicos:

- fiscal_comprovantes → processos.views.fluxo.payment.comprovantes
- fiscal_liquidacoes  → processos.views.fluxo.pre_payment.liquidacoes
- fiscal_documentos   → processos.views.fluxo.pre_payment.cadastro.documentos

Nota: Use imports diretos dos módulos canônicos para novo código.
"""

from .fiscal_reinf import *
from .fiscal_retencoes import *
