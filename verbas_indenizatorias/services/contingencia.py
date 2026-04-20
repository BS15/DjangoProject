"""State machine e regras de negócio para contingências de diárias."""

import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from verbas_indenizatorias.models import ContingenciaDiaria, _CAMPOS_PERMITIDOS_CONTINGENCIA_DIARIA

logger = logging.getLogger(__name__)


def criar_contingencia_diaria(diaria, solicitante, campo_corrigido, valor_proposto, justificativa, valor_anterior=""):
    """Abre uma contingência de retificação para a diária, exigindo aprovação posterior."""
    if campo_corrigido not in _CAMPOS_PERMITIDOS_CONTINGENCIA_DIARIA:
        raise ValidationError(
            f"O campo '{campo_corrigido}' não pode ser retificado via contingência. "
            f"Campos permitidos: {', '.join(sorted(_CAMPOS_PERMITIDOS_CONTINGENCIA_DIARIA))}."
        )

    with transaction.atomic():
        contingencia = ContingenciaDiaria.objects.create(
            diaria=diaria,
            solicitante=solicitante,
            justificativa=justificativa,
            campo_corrigido=campo_corrigido,
            valor_anterior=valor_anterior,
            valor_proposto=valor_proposto,
            status="PENDENTE_SUPERVISOR",
        )

    logger.info(
        "mutation=criar_contingencia_diaria diaria_id=%s contingencia_id=%s campo=%s user_id=%s",
        diaria.pk,
        contingencia.pk,
        campo_corrigido,
        solicitante.pk,
    )
    return contingencia


def _aplicar_contingencia_diaria(contingencia):
    """Aplica o campo proposto à diária, contornando o domain seal de forma controlada."""
    diaria = contingencia.diaria
    campo = contingencia.campo_corrigido
    valor = contingencia.valor_proposto

    if campo not in _CAMPOS_PERMITIDOS_CONTINGENCIA_DIARIA:
        return False, f"Campo '{campo}' não está na lista de campos permitidos."

    if not hasattr(diaria, campo.rstrip("_id")):
        if not hasattr(diaria, campo):
            return False, f"A diária não possui o campo '{campo}'."

    with transaction.atomic():
        setattr(diaria, campo, valor)
        diaria._bypass_domain_seal = True
        try:
            diaria.save(update_fields=[campo])
        finally:
            diaria._bypass_domain_seal = False

    return True, None


def aprovar_contingencia_diaria(contingencia, aprovador, parecer=""):
    """Aprova a contingência e aplica a correção à diária.

    Retorna (sucesso: bool, mensagem_erro: str | None).
    """
    if contingencia.status != "PENDENTE_SUPERVISOR":
        return False, "Esta contingência não está pendente de aprovação."

    sucesso, msg_erro = _aplicar_contingencia_diaria(contingencia)
    if not sucesso:
        return False, msg_erro

    with transaction.atomic():
        contingencia.status = "APROVADA"
        contingencia.aprovado_por = aprovador
        contingencia.data_aprovacao = timezone.now()
        contingencia.parecer = parecer
        contingencia.save(update_fields=["status", "aprovado_por", "data_aprovacao", "parecer"])

    logger.info(
        "mutation=aprovar_contingencia_diaria contingencia_id=%s diaria_id=%s campo=%s user_id=%s",
        contingencia.pk,
        contingencia.diaria_id,
        contingencia.campo_corrigido,
        aprovador.pk,
    )
    return True, None


def rejeitar_contingencia_diaria(contingencia, aprovador, parecer=""):
    """Rejeita a contingência sem aplicar qualquer alteração à diária.

    Retorna (sucesso: bool, mensagem_erro: str | None).
    """
    if contingencia.status != "PENDENTE_SUPERVISOR":
        return False, "Esta contingência não está pendente de análise."

    with transaction.atomic():
        contingencia.status = "REJEITADA"
        contingencia.aprovado_por = aprovador
        contingencia.data_aprovacao = timezone.now()
        contingencia.parecer = parecer
        contingencia.save(update_fields=["status", "aprovado_por", "data_aprovacao", "parecer"])

    logger.info(
        "mutation=rejeitar_contingencia_diaria contingencia_id=%s diaria_id=%s user_id=%s",
        contingencia.pk,
        contingencia.diaria_id,
        aprovador.pk,
    )
    return True, None


__all__ = [
    "criar_contingencia_diaria",
    "aprovar_contingencia_diaria",
    "rejeitar_contingencia_diaria",
]
