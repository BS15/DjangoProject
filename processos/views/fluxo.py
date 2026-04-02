"""Facade de compatibilidade para imports legados do modulo de fluxo.

Mantem suporte a imports historicos como:
	from processos.views.fluxo import <view>

Mesmo com a separacao por dominio em modulos dedicados.
"""

# Base comum e seguranca
from .security import *
from .helpers import *
from .support_views import *

# Fluxo principal por etapa
from .pre_payment import *
from .payment import *
from .post_payment import *

# Endpoints auxiliares transversais
from .api_views import *
from .auditing import *
