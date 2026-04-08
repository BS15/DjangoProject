"""Views e helpers de seguranca/permissoes para acesso a arquivos."""

from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.clickjacking import xframe_options_sameorigin

from ...models import (
    ComprovanteDePagamento,
    Devolucao,
    DespesaSuprimento,
    DocumentoAuxilio,
    DocumentoDiaria,
    DocumentoFiscal,
    DocumentoJeton,
    DocumentoDePagamento,
    DocumentoReembolso,
    RegistroAcessoArquivo,
)


# Mapeia tipos de documentos de verbas ao nome do FK da entidade proprietária
_VERBA_DOC_FK: dict[str, str] = {
    "verba_reembolso_doc": "reembolso",
    "verba_jeton_doc": "jeton",
    "verba_auxilio_doc": "auxilio",
}


def _can_access_verba_beneficiario(user, fk_name, doc):
    """Verifica acesso por e-mail do beneficiário para documentos de verbas simples."""
    entidade = getattr(doc, fk_name, None)
    if not entidade:
        return False
    beneficiario = getattr(entidade, "beneficiario", None)
    return bool(beneficiario and beneficiario.email and beneficiario.email == user.email)


def _is_cap_backoffice(user):
    """
    Verifica se usuário tem permissão explícita de backoffice.
    
    Returns True if user is:
    - Superuser (Django admin with full system access)
    - Has explicit 'pode_operar_contas_pagar' permission (Contas a Pagar role)
    
    NOTE: is_staff flag is intentionally NOT checked here to enforce strict RBAC.
    Staff users must have explicit permissions assigned. See: copilot-instructions.md
    """
    return user.is_active and (
        user.is_superuser
        or user.has_perm("processos.pode_operar_contas_pagar")
    )


def _resolver_documento(tipo_documento, documento_id):
    """Resolve o documento alvo e retorna (objeto_doc, field_arquivo_name)."""
    resolvers = {
        "processo": (DocumentoDePagamento, "arquivo"),
        "fiscal": (DocumentoFiscal, "documento_vinculado"),
        "comprovante": (ComprovanteDePagamento, "arquivo"),
        "suprimento": (DespesaSuprimento, "arquivo"),
        "devolucao": (Devolucao, "comprovante"),
        "verba_diaria_doc": (DocumentoDiaria, "arquivo"),
        "verba_reembolso_doc": (DocumentoReembolso, "arquivo"),
        "verba_jeton_doc": (DocumentoJeton, "arquivo"),
        "verba_auxilio_doc": (DocumentoAuxilio, "arquivo"),
    }
    model_and_field = resolvers.get(tipo_documento)
    if not model_and_field:
        raise Http404
    model_cls, file_attr = model_and_field
    return get_object_or_404(model_cls, id=documento_id), file_attr


def _can_access_non_backoffice(user, tipo_documento, doc):
    """Valida acesso de usuarios nao-backoffice por tipo de documento."""
    if tipo_documento in {"processo", "comprovante", "devolucao"}:
        return False

    if tipo_documento == "fiscal":
        return doc.fiscal_contrato == user

    if tipo_documento == "suprimento":
        user_in_supridos = user.groups.filter(name="SUPRIDOS").exists()
        suprimento = doc.suprimento
        is_encerrado = (
            suprimento.status is not None
            and suprimento.status.status_choice.upper() == "ENCERRADO"
        )
        suprido_email = suprimento.suprido.email if suprimento.suprido else None
        email_match = bool(suprido_email and suprido_email == user.email)
        return user_in_supridos and not is_encerrado and email_match

    if tipo_documento == "verba_diaria_doc":
        diaria = doc.diaria
        email_match = bool(
            diaria.beneficiario
            and diaria.beneficiario.email
            and diaria.beneficiario.email == user.email
        )
        proponente_match = diaria.proponente == user
        return email_match or proponente_match

    if tipo_documento in _VERBA_DOC_FK:
        return _can_access_verba_beneficiario(user, _VERBA_DOC_FK[tipo_documento], doc)

    return False


@xframe_options_sameorigin
def download_arquivo_seguro(request, tipo_documento, documento_id):
    doc, file_attr = _resolver_documento(tipo_documento, documento_id)

    # DocumentoFiscal guarda o arquivo real em documento_vinculado.arquivo.
    if tipo_documento == "fiscal":
        if not doc.documento_vinculado:
            raise Http404
        arquivo = doc.documento_vinculado.arquivo
    else:
        arquivo = getattr(doc, file_attr, None)

    if not _is_cap_backoffice(request.user) and not _can_access_non_backoffice(
        request.user, tipo_documento, doc
    ):
        raise PermissionDenied

    if not arquivo or not arquivo.name:
        raise Http404

    try:
        file_handle = arquivo.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404

    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")

    RegistroAcessoArquivo.objects.create(
        usuario=request.user,
        nome_arquivo=arquivo.name,
        ip_address=ip,
    )

    return FileResponse(file_handle, as_attachment=False)


__all__ = ["_is_cap_backoffice", "download_arquivo_seguro"]
