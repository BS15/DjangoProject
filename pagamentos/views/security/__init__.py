"""Download seguro de arquivos com validação de acesso por contexto de negócio."""

from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404

from commons.shared.access_utils import user_is_entity_owner
from pagamentos.models import (
    ComprovantePagamento,
    DevolucaoProcessual,
    DocumentoOrcamentarioProcessual,
    DocumentoProcessual,
    RegistroAcessoArquivoProcessual,
)
from suprimentos.models import DespesaSuprimento
from verbas_indenizatorias.models import (
    DocumentoAuxilio,
    DocumentoComprovacao,
    DocumentoDiaria,
    DocumentoJeton,
    DocumentoReembolso,
)


def _resolve_documento(tipo_documento, documento_id):
    """Resolve documento e objeto-pai para validação de acesso."""
    if tipo_documento == "processo":
        documento = get_object_or_404(DocumentoProcessual, id=documento_id)
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
        from fiscal.models import DocumentoFiscal

        documento = get_object_or_404(DocumentoFiscal, id=documento_id)
        documento_vinculado = documento.documento_vinculado
        if not documento_vinculado or not getattr(documento_vinculado, "arquivo", None):
            raise Http404("Documento fiscal sem arquivo vinculado.")
        return documento_vinculado, documento.processo
    if tipo_documento == "suprimento":
        documento = get_object_or_404(DespesaSuprimento, id=documento_id)
        return documento, documento.suprimento
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
    raise Http404("Tipo de documento inválido.")


def _has_access(user, tipo_documento, objeto_pai):
    """Valida autorização para download do arquivo solicitado."""
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser or user.has_perm("pagamentos.pode_auditar_conselho"):
        return True

    if tipo_documento == "verba_diaria_comprov":
        from verbas_indenizatorias.views.diarias.access import _pode_acessar_prestacao

        return _pode_acessar_prestacao(user, objeto_pai)

    return user_is_entity_owner(user, objeto_pai)


def download_arquivo_seguro(request, tipo_documento, documento_id):
    """Faz download do arquivo quando usuário possui autorização contextual."""
    documento, objeto_pai = _resolve_documento(tipo_documento, documento_id)

    if not _has_access(request.user, tipo_documento, objeto_pai):
        return HttpResponseForbidden("Acesso negado a este arquivo.")

    arquivo = getattr(documento, "arquivo", None) or getattr(documento, "comprovante", None)
    if not arquivo:
        raise Http404("Arquivo não encontrado.")

    nome_arquivo = (arquivo.name or "documento").split("/")[-1]
    RegistroAcessoArquivoProcessual.objects.create(
        usuario=request.user,
        nome_arquivo=nome_arquivo,
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    arquivo.open("rb")
    return FileResponse(arquivo, as_attachment=False, filename=nome_arquivo)


__all__ = ["download_arquivo_seguro"]
