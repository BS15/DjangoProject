"""Services canônicos do domínio fiscal."""

from .reinf import (
    _build_r2010_xml,
    _build_r4020_xml,
    gerar_lotes_reinf,
    get_serie_2000_data,
    get_serie_4000_data,
)

__all__ = [
    '_build_r2010_xml',
    '_build_r4020_xml',
    'gerar_lotes_reinf',
    'get_serie_2000_data',
    'get_serie_4000_data',
]