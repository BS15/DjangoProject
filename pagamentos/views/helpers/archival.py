"""Compat: helper de arquivamento delegado ao serviço canônico."""

from pagamentos.services.arquivamento import executar_arquivamento_definitivo


def _executar_arquivamento_definitivo(processo, usuario):
    """Compatibilidade: delega arquivamento ao serviço canônico."""
    return executar_arquivamento_definitivo(processo, usuario)


__all__ = [
    "_executar_arquivamento_definitivo",
]
