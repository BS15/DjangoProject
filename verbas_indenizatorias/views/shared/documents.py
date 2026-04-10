"""Operacoes de upload e persistencia de documentos de verbas."""

import logging
import os

from django.contrib import messages
from django.db import DatabaseError, transaction


logger = logging.getLogger(__name__)

_EXTENSOES_DOCUMENTO_PERMITIDAS = {".pdf", ".jpg", ".jpeg", ".png"}


def _extensao_documento_permitida(nome_arquivo):
    """Valida se a extensão do arquivo está entre os formatos permitidos."""
    _, ext = os.path.splitext(nome_arquivo.lower())
    return ext in _EXTENSOES_DOCUMENTO_PERMITIDAS


def _anexar_documento(modelo_documento, fk_name, entidade, arquivo, tipo_id):
    """Cria o registro de documento vinculado à entidade de verba informada."""
    kwargs = {fk_name: entidade, "arquivo": arquivo, "tipo_id": tipo_id}
    return modelo_documento.objects.create(**kwargs)


def _obter_dados_upload_documento(request, *, arquivo_field="arquivo", tipo_field="tipo"):
    """Extrai arquivo e tipo documental do payload da requisição."""
    return request.FILES.get(arquivo_field), request.POST.get(tipo_field)


def _validar_upload_documento(arquivo, tipo_id, *, obrigatorio=True):
    """Valida presença e extensão do upload documental."""
    if not arquivo and not tipo_id and not obrigatorio:
        return None

    if not arquivo or not tipo_id:
        return "Selecione um arquivo e um tipo de documento."

    if not _extensao_documento_permitida(arquivo.name):
        return "Formato de arquivo não permitido. Use PDF, JPG ou PNG."

    return None


def _salvar_documento_upload(
    entidade,
    *,
    modelo_documento,
    fk_name,
    arquivo,
    tipo_id,
    obrigatorio=True,
):
    """Valida e persiste um documento de verba, retornando `(documento, erro)` ."""
    erro = _validar_upload_documento(arquivo, tipo_id, obrigatorio=obrigatorio)
    if erro:
        return None, erro

    if not arquivo:
        return None, None

    try:
        return _anexar_documento(modelo_documento, fk_name, entidade, arquivo, tipo_id), None
    except (DatabaseError, OSError, TypeError, ValueError) as exc:
        logger.exception(
            "Erro ao salvar documento de verba para entidade %s: %s",
            getattr(entidade, "id", None),
            exc,
        )
        return None, "Erro ao salvar o documento. Tente novamente."


def _processar_upload_documento(request, entidade, modelo_documento, fk_name):
    """Processa upload de documento, valida entrada e persiste o anexo."""
    arquivo, tipo_id = _obter_dados_upload_documento(request)
    _, erro = _salvar_documento_upload(
        entidade,
        modelo_documento=modelo_documento,
        fk_name=fk_name,
        arquivo=arquivo,
        tipo_id=tipo_id,
    )
    if erro:
        messages.error(request, erro)
        return False

    messages.success(request, "Documento anexado com sucesso!")
    return True


def _salvar_verba_com_anexo_opcional(
    request,
    *,
    form,
    modelo_documento,
    fk_name,
    pre_save=None,
    post_save=None,
):
    """Salva uma verba e anexa documento opcional em transação atômica."""
    arquivo, tipo_id = _obter_dados_upload_documento(
        request,
        arquivo_field="documento_anexo",
        tipo_field="tipo_documento_anexo",
    )
    erro = _validar_upload_documento(arquivo, tipo_id, obrigatorio=False)
    if erro:
        messages.error(request, erro)
        return None

    with transaction.atomic():
        instancia = form.save(commit=False)
        if pre_save:
            pre_save(instancia)
        instancia.save()

        if hasattr(form, "save_m2m"):
            form.save_m2m()

        if post_save:
            post_save(instancia)

        if arquivo:
            _anexar_documento(modelo_documento, fk_name, instancia, arquivo, tipo_id)

    return instancia


def _processar_edicao_verba_com_upload(
    request,
    *,
    instancia,
    form_class,
    modelo_documento,
    fk_name,
    success_message,
):
    """Processa fluxo padrao de edicao com upload avulso de documento."""
    if request.method == "POST" and request.POST.get("upload_doc"):
        _processar_upload_documento(request, instancia, modelo_documento, fk_name)
        return None, True

    if request.method == "POST":
        form = form_class(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            messages.success(request, success_message)
            return None, True
        messages.error(request, "Erro ao salvar. Verifique os campos.")
        return form, False

    return form_class(instance=instancia), False
