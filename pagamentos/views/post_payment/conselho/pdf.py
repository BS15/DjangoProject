"""PDF views da etapa de conselho fiscal."""

# A implementação canônica vive em fluxo.views.pdf para evitar duplicação.
from pagamentos.views.pdf import gerar_parecer_conselho_view  # noqa: F401

__all__ = ["gerar_parecer_conselho_view"]
