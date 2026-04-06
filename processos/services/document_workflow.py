"""Orquestra workflows documentais (gerar, anexar, assinar e responder PDF)."""

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db.models import Max
from django.http import HttpResponse

from processos.pdf_generators import gerar_documento_pdf


def gerar_documento_bytes(doc_type, obj, **kwargs):
    """Gera bytes de PDF para um tipo documental registrado."""
    return gerar_documento_pdf(doc_type, obj, **kwargs)


def montar_resposta_pdf(pdf_bytes, nome_arquivo, inline=True):
    """Cria resposta HTTP padronizada para exibição/download de PDF."""
    disposition = "inline" if inline else "attachment"
    if hasattr(pdf_bytes, "read"):
        try:
            pdf_bytes.seek(0)
        except Exception:
            pass
        content = pdf_bytes.read()
    else:
        content = pdf_bytes

    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'{disposition}; filename="{nome_arquivo}"'
    return response


def gerar_resposta_pdf(doc_type, obj, nome_arquivo, inline=True, **kwargs):
    """Gera PDF e retorna resposta HTTP padronizada em uma única chamada."""
    pdf_bytes = gerar_documento_bytes(doc_type, obj, **kwargs)
    return montar_resposta_pdf(pdf_bytes, nome_arquivo, inline=inline)


def gerar_e_anexar_documento_processo(processo, doc_type, obj, nome_arquivo, tipo_documento_nome, **kwargs):
    """Gera PDF e anexa ao processo com proteção de duplicidade por nome."""
    if processo.documentos.filter(arquivo__icontains=nome_arquivo).exists():
        return False

    pdf_bytes = gerar_documento_bytes(doc_type, obj, **kwargs)
    return processo._anexar_pdf_gerado(pdf_bytes, nome_arquivo, tipo_documento_nome)


def criar_assinatura_rascunho(entidade, tipo_documento, criador, pdf_bytes, nome_arquivo):
    """Cria registro de assinatura Autentique em rascunho com PDF associado."""
    from processos.models.segments.auxiliary import AssinaturaAutentique

    assinatura = AssinaturaAutentique(
        content_type=ContentType.objects.get_for_model(entidade),
        object_id=entidade.id,
        tipo_documento=tipo_documento,
        criador=criador,
        status="RASCUNHO",
    )
    assinatura.arquivo.save(nome_arquivo, ContentFile(pdf_bytes), save=True)
    return assinatura


def construir_signatarios_padrao(entidade, extra_emails=None):
    """Monta lista padrão de signatários com base na entidade relacionada.

    A resolução tenta cobrir entidades além de Diária, priorizando atributos
    comuns do domínio (beneficiário, proponente, credor e aprovadores).
    """
    if entidade is None:
        return []

    campos_prioritarios = (
        "beneficiario",
        "proponente",
        "credor",
        "suprido",
        "solicitante",
        "fiscal_contrato",
        "criador",
        "aprovado_por_supervisor",
        "aprovado_por_ordenador",
        "aprovado_por_conselho",
    )

    emails = []
    for campo in campos_prioritarios:
        candidato = getattr(entidade, campo, None)
        email = getattr(candidato, "email", None) if candidato else None
        if email:
            emails.append(email)

    if extra_emails:
        for email in extra_emails:
            if email:
                emails.append(email)

    vistos = set()
    signatarios = []
    for email in emails:
        if email in vistos:
            continue
        vistos.add(email)
        signatarios.append({"email": email, "action": "SIGN"})

    return signatarios


def enviar_para_assinatura(entidade, tipo_documento, nome_doc, signatarios, doc_type=None, pdf_bytes=None, **kwargs):
    """Gera (quando necessário) e envia um documento para assinatura no Autentique."""
    from processos.autentique_service import enviar_documento_para_assinatura
    from processos.models.segments.auxiliary import AssinaturaAutentique

    ct = ContentType.objects.get_for_model(entidade)
    assinatura_existente = AssinaturaAutentique.objects.filter(
        content_type=ct,
        object_id=entidade.pk,
        tipo_documento=tipo_documento,
        status='PENDENTE',
    ).first()
    if assinatura_existente:
        return assinatura_existente

    if pdf_bytes is None:
        if not doc_type:
            raise ValueError("doc_type é obrigatório quando pdf_bytes não for informado.")
        pdf_bytes = gerar_documento_bytes(doc_type, entidade, **kwargs)

    resultado = enviar_documento_para_assinatura(pdf_bytes, nome_doc, signatarios)

    return AssinaturaAutentique.objects.create(
        content_type=ct,
        object_id=entidade.pk,
        tipo_documento=tipo_documento,
        autentique_id=resultado["id"],
        autentique_url=resultado["url"],
        dados_signatarios=resultado["signers_data"],
        status='PENDENTE',
    )


def disparar_assinatura_rascunho(assinatura, signatarios, nome_doc=None):
    """Dispara um rascunho de assinatura já anexado para o Autentique."""
    from processos.autentique_service import enviar_documento_para_assinatura

    if not assinatura.arquivo:
        raise ValueError("Nenhum arquivo de rascunho encontrado para este documento.")

    with assinatura.arquivo.open("rb") as f:
        pdf_bytes = f.read()

    nome = nome_doc or f"{assinatura.tipo_documento}_{assinatura.id}"
    resultado = enviar_documento_para_assinatura(pdf_bytes, nome, signatarios)

    assinatura.autentique_id = resultado["id"]
    assinatura.autentique_url = resultado["url"]
    assinatura.dados_signatarios = resultado["signers_data"]
    assinatura.status = 'PENDENTE'
    assinatura.save()
    return assinatura


def disparar_assinatura_rascunho_com_signatarios(assinatura):
    """Resolve signatários padrão e dispara um rascunho de assinatura.

    Retorna None quando não há entidade relacionada ou quando não for
    possível determinar signatários para o documento.
    """
    entidade = assinatura.entidade_relacionada
    if entidade is None:
        return None

    signatarios = construir_signatarios_padrao(entidade)
    if not signatarios:
        return None

    nome_doc = f"{assinatura.tipo_documento}_{assinatura.id}"
    return disparar_assinatura_rascunho(assinatura, signatarios, nome_doc=nome_doc)


def sincronizar_assinatura(assinatura):
    """Sincroniza assinatura no Autentique e atualiza arquivo assinado quando concluída.

    Retorna uma string de estado: signed, pending ou already_signed.
    """
    from processos.autentique_service import verificar_e_baixar_documento

    if assinatura.status == "ASSINADO":
        return "already_signed"

    resultado = verificar_e_baixar_documento(assinatura.autentique_id)
    if not resultado["assinado"]:
        return "pending"

    nome_arquivo = f"{assinatura.tipo_documento}_Assinado_{assinatura.id}.pdf"
    assinatura.arquivo_assinado.save(nome_arquivo, ContentFile(resultado["pdf_bytes"]), save=False)
    assinatura.status = "ASSINADO"
    assinatura.save()
    return "signed"


def gerar_e_anexar_scd_diaria(diaria, criador):
    """Gera SCD da diária, anexa DocumentoDiaria e cria rascunho de assinatura."""
    from processos.models.segments.documents import DocumentoDiaria
    from processos.models.segments.parametrizations import TiposDeDocumento

    pdf_bytes = gerar_documento_bytes('scd', diaria)

    tipo_scd, _ = TiposDeDocumento.objects.get_or_create(
        tipo_de_documento__iexact='SOLICITAÇÃO DE CONCESSÃO DE DIÁRIAS (SCD)',
        defaults={'tipo_de_documento': 'SOLICITAÇÃO DE CONCESSÃO DE DIÁRIAS (SCD)'},
    )
    proxima_ordem = (diaria.documentos.aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1
    DocumentoDiaria.objects.create(
        diaria=diaria,
        arquivo=ContentFile(pdf_bytes, name=f"SCD_{diaria.id}.pdf"),
        tipo=tipo_scd,
        ordem=proxima_ordem,
    )
    return criar_assinatura_rascunho(
        entidade=diaria,
        tipo_documento='SCD',
        criador=criador,
        pdf_bytes=pdf_bytes,
        nome_arquivo=f"SCD_{diaria.id}.pdf",
    )
