"""Pacote de endpoints de verbas indenizatorias.

Mantem compatibilidade de importacao enquanto organiza responsabilidades
em subpacotes por processo e por tipo de verba.
"""

from .processo import *
from .siscac_diarias_sync import *
from .tipos.auxilios import *
from .tipos.diarias import *
from .tipos.jetons import *
from .tipos.reembolsos import *
