"""Download seguro de arquivos com validação de acesso por contexto de negócio."""

import os
import re
from urllib.parse import quote

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.views.decorators.clickjacking import xframe_options_sameorigin

from commons.shared.access_utils import user_is_entity_owner
from apps.pagamentos.models import (
    AssinaturaEletronica,
    ComprovantePagamento,
    DevolucaoProcessual,
    DocumentoOrcamentarioProcessual,
    DocumentoProcesso,
    RegistroAcessoArquivoProcessual,
)
from apps.suprimentos.models import DespesaSuprimento, PrestacaoContasSuprimento
from apps.verbas_indenizatorias.models import (
    DocumentoAuxilio,
    DocumentoComprovacao,
    DocumentoDiaria,
    DocumentoJeton,
    DocumentoReembolso,
)


def _resolve_documento(tipo_documento, documento_id):
    """Resolve documento e objeto-pai para validação de acesso."""
    if tipo_documento == "processo":
        documento = get_object_or_404(DocumentoProcesso, id=documento_id)
        return documento, documento.processo
    if tipo_documento == "orcamentario":
        documento = get_object_or_404(DocumentoOrcamentarioProcessual, id=documento_id)
        return documento, documento.processo
    if tipo_documento == "comprovante_pagamento":
        documento = get_object_or_404(ComprovantePagamento, id=documento_id)
        return documento, documento.processo
    if tipo_documento == "devolucao":
        documento = get_object_or_404(DevolucaoProcessual, id=documento_id)
        return documento, documento.processo
    if tipo_documento == "fiscal":
        from apps.retencoes.models import DocumentoFiscal

        documento = get_object_or_404(DocumentoFiscal, id=documento_id)
        documento_vinculado = documento.documento_vinculado
        if not documento_vinculado or not getattr(documento_vinculado, "arquivo", None):
            raise Http404("Documento fiscal sem arquivo vinculado.")
        return documento_vinculado, documento.processo
    if tipo_documento == "suprimento":
        documento = get_object_or_404(DespesaSuprimento, id=documento_id)
        return documento, documento.suprimento
    if tipo_documento == "suprimento_prestacao":
        prestacao = get_object_or_404(PrestacaoContasSuprimento, id=documento_id)
        return prestacao, prestacao.suprimento
    if tipo_documento == "verba_diaria_doc":
        documento = get_object_or_404(DocumentoDiaria, id=documento_id)
        return documento, documento.diaria
    if tipo_documento == "verba_diaria_comprov":
        documento = get_object_or_404(DocumentoComprovacao, id=documento_id)
        return documento, documento.prestacao.diaria
    if tipo_documento == "verba_reembolso_doc":
        documento = get_object_or_404(DocumentoReembolso, id=documento_id)
        return documento, documento.reembolso
    if tipo_documento == "verba_jeton_doc":
        documento = get_object_or_404(DocumentoJeton, id=documento_id)
        return documento, documento.jeton
    if tipo_documento == "verba_auxilio_doc":
        documento = get_object_or_404(DocumentoAuxilio, id=documento_id)
        return documento, documento.auxilio
    if tipo_documento in ("assinatura_rascunho", "assinatura_assinado"):
        assinatura = get_object_or_404(AssinaturaEletronica, id=documento_id)
        return assinatura, assinatura
    raise Http404("Tipo de documento inválido.")


def _has_access(user, tipo_documento, objeto_pai):
    """Valida autorização para download do arquivo solicitado."""
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser or user.has_perm("pagamentos.pode_auditar_conselho"):
        return True

    if tipo_documento == "verba_diaria_comprov":
        from apps.verbas_indenizatorias.views.diarias.access import _pode_acessar_prestacao

        return _pode_acessar_prestacao(user, objeto_pai)

    if tipo_documento in ("assinatura_rascunho", "assinatura_assinado"):
        assinatura = objeto_pai
        return assinatura.criador == user or user.has_perm("pagamentos.operador_contas_a_pagar")

    return user_is_entity_owner(user, objeto_pai)


def _get_arquivo(documento, tipo_documento):
    """Retorna o campo de arquivo correspondente ao tipo de documento."""
    if tipo_documento == "assinatura_rascunho":
        return getattr(documento, "arquivo", None)
    if tipo_documento == "assinatura_assinado":
        return getattr(documento, "arquivo_assinado", None)
    return (
        getattr(documento, "arquivo", None)
        or getattr(documento, "comprovante", None)
        or getattr(documento, "comprovante_devolucao", None)
    )


@xframe_options_sameorigin
def download_arquivo_seguro(request, tipo_documento, documento_id):
    """Faz download do arquivo quando usuário possui autorização contextual.

    Delega a entrega do arquivo ao nginx via X-Accel-Redirect para que o
    processo Django não bloqueie durante a transferência. O nginx deve ter a
    diretiva ``internal`` configurada no location /media/.
    """
    documento, objeto_pai = _resolve_documento(tipo_documento, documento_id)

    if not _has_access(request.user, tipo_documento, objeto_pai):
        return HttpResponseForbidden("Acesso negado a este arquivo.")

    arquivo = _get_arquivo(documento, tipo_documento)
    if not arquivo:
        raise Http404("Arquivo não encontrado.")

    nome_arquivo = (arquivo.name or "documento").split("/")[-1]
    RegistroAcessoArquivoProcessual.objects.create(
        usuario=request.user,
        nome_arquivo=nome_arquivo,
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    # Validate that the resolved absolute path stays inside MEDIA_ROOT to
    # prevent path traversal via manipulated FileField values.
    media_root = os.path.abspath(settings.MEDIA_ROOT)
    abs_path = os.path.abspath(os.path.join(media_root, arquivo.name))
    if not abs_path.startswith(media_root + os.sep):
        raise Http404("Caminho de arquivo inválido.")

    # Build a safe relative path (forward slashes, percent-encoded) for the
    # X-Accel-Redirect header that nginx will serve.
    relative = os.path.relpath(abs_path, media_root).replace(os.sep, "/")
    accel_path = "/media/" + quote(relative, safe="/")

    # Sanitize the filename for the Content-Disposition header to prevent
    # header injection (strip control chars and double-quotes).
    safe_filename = re.sub(r'[\x00-\x1f"]', "_", nome_arquivo)

    response = HttpResponse()
    response["X-Accel-Redirect"] = accel_path
    response["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(safe_filename)}"
    response["X-Content-Type-Options"] = "nosniff"
    return response


__all__ = ["download_arquivo_seguro"]

