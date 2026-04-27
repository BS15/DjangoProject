"""Serviços canônicos para ciclo de prestação de contas de diárias."""

import logging

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils import timezone

from commons.shared.document_services import obter_proxima_ordem_documento
from pagamentos.models import DocumentoProcesso
from verbas_indenizatorias.models import DocumentoComprovacao, PrestacaoContasDiaria

logger = logging.getLogger(__name__)


def obter_ou_criar_prestacao(diaria):
    """Obtém prestação da diária em estado aberto quando ainda inexistente."""
    prestacao, _ = PrestacaoContasDiaria.objects.get_or_create(
        diaria=diaria,
        defaults={"status": PrestacaoContasDiaria.STATUS_ABERTA},
    )
    return prestacao


def registrar_comprovante(diaria, arquivo, tipo_id):
    """Registra comprovante na prestação, bloqueando inclusão quando encerrada."""
    prestacao = obter_ou_criar_prestacao(diaria)
    if prestacao.status == PrestacaoContasDiaria.STATUS_ENCERRADA:
        raise ValidationError("A prestação de contas desta diária já foi encerrada.")

    proxima_ordem = obter_proxima_ordem_documento(prestacao.documentos)
    return DocumentoComprovacao.objects.create(
        prestacao=prestacao,
        arquivo=arquivo,
        tipo_id=tipo_id,
        ordem=proxima_ordem,
    )


def encerrar_prestacao(prestacao, user):
    """Encerra a prestação de contas e registra metadados de auditoria."""
    if prestacao.status == PrestacaoContasDiaria.STATUS_ENCERRADA:
        return prestacao

    prestacao.status = PrestacaoContasDiaria.STATUS_ENCERRADA
    prestacao.encerrado_em = timezone.now()
    prestacao.encerrado_por = user
    prestacao.save(update_fields=["status", "encerrado_em", "encerrado_por"])
    return prestacao


def _anexar_comprovantes_ao_processo(prestacao, processo):
    """Replica comprovantes da prestação como documentos do processo vinculado."""
    for comprovante in prestacao.documentos.select_related("tipo").all().order_by("ordem", "id"):
        nome_arquivo = comprovante.arquivo.name.rsplit("/", 1)[-1] or f"comprovante_{comprovante.id}"
        comprovante.arquivo.open("rb")
        try:
            conteudo = comprovante.arquivo.read()
        finally:
            try:
                comprovante.arquivo.close()
            except Exception as exc:
                logger.warning(
                    "evento=erro_ao_fechar_arquivo_comprovante comprovante_id=%s erro=%s",
                    comprovante.id,
                    exc,
                )

        DocumentoProcesso.objects.create(
            processo=processo,
            arquivo=ContentFile(conteudo, name=nome_arquivo),
            tipo=comprovante.tipo,
            ordem=obter_proxima_ordem_documento(processo.documentos),
        )


def aceitar_prestacao(prestacao, user, processo):
    """Aceita a prestação, anexa comprovantes ao processo e encerra o ciclo."""
    if not processo:
        raise ValidationError("A diária precisa estar vinculada a um processo para aceitar a prestação.")

    _anexar_comprovantes_ao_processo(prestacao, processo)
    return encerrar_prestacao(prestacao, user)
