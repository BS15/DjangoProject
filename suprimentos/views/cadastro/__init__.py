"""Endpoints da etapa de cadastro de suprimentos."""

from .actions import *
from .forms import *

__all__ = ["add_suprimento_view", "persistir_suprimento_com_processo"]
