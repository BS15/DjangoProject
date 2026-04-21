"""Serviços canônicos para o ciclo de prestação de contas de suprimentos de fundos."""

import logging

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def obter_ou_criar_prestacao_suprimento(suprimento):
    """Obtém ou cria a prestação de contas do suprimento em estado aberto."""
    from suprimentos.models import PrestacaoContasSuprimento

    prestacao, _ = PrestacaoContasSuprimento.objects.get_or_create(
        suprimento=suprimento,
        defaults={"status": PrestacaoContasSuprimento.STATUS_ABERTA},
    )
    return prestacao


def enviar_prestacao_suprimento(prestacao, comprovante, data_devolucao, user):
    """Registra o envio da prestação pelo responsável e avança para Aguardando Revisão.

    Valida que o comprovante de devolução foi fornecido quando existe saldo remanescente.
    """
    from suprimentos.models import PrestacaoContasSuprimento

    if prestacao.status == PrestacaoContasSuprimento.STATUS_ENCERRADA:
        raise ValidationError("Esta prestação de contas já foi encerrada.")

    suprimento = prestacao.suprimento
    saldo = suprimento.saldo_remanescente

    if saldo > 0 and not comprovante:
        raise ValidationError(
            "O comprovante de devolução do saldo remanescente é obrigatório."
        )

    with transaction.atomic():
        if comprovante:
            prestacao.comprovante_devolucao = comprovante
        if data_devolucao:
            prestacao.data_devolucao = data_devolucao
        prestacao.termo_fidedignidade_assinado = True
        prestacao.status = PrestacaoContasSuprimento.STATUS_ENVIADA
        prestacao.submetido_em = timezone.now()
        prestacao.submetido_por = user
        prestacao.save(
            update_fields=[
                "comprovante_devolucao",
                "data_devolucao",
                "termo_fidedignidade_assinado",
                "status",
                "submetido_em",
                "submetido_por",
            ]
        )
        logger.info(
            "mutation=enviar_prestacao_suprimento suprimento_id=%s prestacao_id=%s user_id=%s",
            suprimento.pk,
            prestacao.pk,
            user.pk,
        )

    return prestacao


def encerrar_prestacao_suprimento(prestacao, user):
    """Operador encerra a prestação: registra devolução automática e avança o processo.

    Quando o suprimento possui saldo remanescente (valor não gasto):
      1. Cria DevolucaoProcessual com o saldo restante, usando o comprovante da prestação.
      2. Avança o Processo vinculado para 'PAGO - EM CONFERÊNCIA'.
      3. Marca o suprimento como ENCERRADO.
      4. Fecha a prestação com status ENCERRADA.
    """
    from suprimentos.models import PrestacaoContasSuprimento
    from suprimentos.views.helpers import _atualizar_status_apos_fechamento
    from pagamentos.models import Devolucao

    if prestacao.status == PrestacaoContasSuprimento.STATUS_ENCERRADA:
        raise ValidationError("Esta prestação de contas já está encerrada.")

    suprimento = prestacao.suprimento
    saldo = suprimento.saldo_remanescente

    with transaction.atomic():
        # Auto-register devolution when there is unused balance.
        if saldo > 0:
            processo = suprimento.processo
            if not processo:
                raise ValidationError(
                    "Suprimento sem processo vinculado: não é possível registrar devolução."
                )

            comprovante_content = None
            if prestacao.comprovante_devolucao and prestacao.comprovante_devolucao.name:
                prestacao.comprovante_devolucao.open("rb")
                try:
                    raw = prestacao.comprovante_devolucao.read()
                finally:
                    try:
                        prestacao.comprovante_devolucao.close()
                    except Exception:
                        logger.warning(
                            "Falha ao fechar comprovante_devolucao da prestacao %s após leitura.",
                            prestacao.pk,
                        )
                nome = (
                    prestacao.comprovante_devolucao.name.rsplit("/", 1)[-1]
                    or f"comprovante_saldo_suprimento_{suprimento.pk}.pdf"
                )
                comprovante_content = ContentFile(raw, name=nome)
            else:
                raise ValidationError(
                    "Comprovante de devolução ausente: não é possível encerrar sem o comprovante."
                )

            data_dev = prestacao.data_devolucao or timezone.now().date()
            Devolucao.objects.create(
                processo=processo,
                valor_devolvido=saldo,
                data_devolucao=data_dev,
                motivo=(
                    f"Devolução automática de saldo remanescente do suprimento #{suprimento.pk}. "
                    f"Valor gasto: R$ {suprimento.valor_gasto}. "
                    f"Saldo devolvido: R$ {saldo}."
                ),
                comprovante=comprovante_content,
            )

            logger.info(
                "mutation=auto_devolucao_suprimento suprimento_id=%s processo_id=%s valor=%s user_id=%s",
                suprimento.pk,
                processo.pk,
                saldo,
                user.pk,
            )

        # Advance processo to PAGO - EM CONFERÊNCIA and mark suprimento ENCERRADO.
        _atualizar_status_apos_fechamento(suprimento)

        # Close the prestação.
        prestacao.status = PrestacaoContasSuprimento.STATUS_ENCERRADA
        prestacao.encerrado_em = timezone.now()
        prestacao.encerrado_por = user
        prestacao.save(update_fields=["status", "encerrado_em", "encerrado_por"])

        logger.info(
            "mutation=encerrar_prestacao_suprimento suprimento_id=%s prestacao_id=%s user_id=%s",
            suprimento.pk,
            prestacao.pk,
            user.pk,
        )

    return prestacao
