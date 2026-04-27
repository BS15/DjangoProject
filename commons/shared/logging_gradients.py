"""Helpers para padronizar severidade de logs por criticidade de dominio.

Gradiente recomendado:
- audit (info): trilha normal de operacao
- recoverable (warning): falha tratada com continuidade do fluxo
- critical (error): falha de etapa critica com impacto operacional
"""


def _serialize_context(context):
    if not context:
        return ""
    parts = []
    for key, value in context.items():
        parts.append(f"{key}={value}")
    return " ".join(parts)


def log_audit(logger, event, **context):
    extra = _serialize_context(context)
    if extra:
        logger.info("classe=audit evento=%s %s", event, extra)
        return
    logger.info("classe=audit evento=%s", event)


def log_recoverable(logger, event, exc=None, **context):
    if exc is not None:
        context["erro"] = exc
    extra = _serialize_context(context)
    if extra:
        logger.warning("classe=recuperavel evento=%s %s", event, extra)
        return
    logger.warning("classe=recuperavel evento=%s", event)


def log_critical(logger, event, exc=None, **context):
    if exc is not None:
        context["erro"] = exc
    extra = _serialize_context(context)
    if extra:
        logger.error("classe=critico evento=%s %s", event, extra)
        return
    logger.error("classe=critico evento=%s", event)


__all__ = [
    "log_audit",
    "log_recoverable",
    "log_critical",
]
