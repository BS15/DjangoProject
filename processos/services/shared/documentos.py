"""Orquestra operações documentais compartilhadas entre workflows."""

import logging

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.http import HttpResponse

from processos.pdf_generators import gerar_documento_pdf
from .errors import AssinaturaSignatariosError


logger = logging.getLogger(__name__)


def gerar_documento_bytes(doc_type, obj, **kwargs):
    """Gera bytes de PDF para um tipo documental registrado."""
    return gerar_documento_pdf(doc_type, obj, **kwargs)


def montar_resposta_pdf(pdf_bytes, nome_arquivo, inline=True):
    """Cria resposta HTTP padronizada para exibição/download de PDF."""
    disposition = 'inline' if inline else 'attachment'
    if hasattr(pdf_bytes, 'read'):
        try:
            pdf_bytes.seek(0)
        except (AttributeError, OSError) as exc:
            logger.warning(
                "Stream PDF não suportou seek em '%s': %s",
                nome_arquivo,
                exc,
            )
        content = pdf_bytes.read()
    else:
        content = pdf_bytes

    response = HttpResponse(content, content_type='application/pdf')
    response['Content-Disposition'] = f'{disposition}; filename="{nome_arquivo}"'
    return response


def gerar_resposta_pdf(doc_type, obj, nome_arquivo, inline=True, **kwargs):
    """Gera PDF e retorna resposta HTTP padronizada em uma única chamada."""
    pdf_bytes = gerar_documento_bytes(doc_type, obj, **kwargs)
    return montar_resposta_pdf(pdf_bytes, nome_arquivo, inline=inline)


def criar_assinatura_rascunho(entidade, tipo_documento, criador, pdf_bytes, nome_arquivo):
    """Cria registro de assinatura Autentique em rascunho com PDF associado."""
    from processos.models.segments.auxiliary import AssinaturaAutentique

    assinatura = AssinaturaAutentique(
        content_type=ContentType.objects.get_for_model(entidade),
        object_id=entidade.id,
        tipo_documento=tipo_documento,
        criador=criador,
        status='RASCUNHO',
    )
    assinatura.arquivo.save(nome_arquivo, ContentFile(pdf_bytes), save=True)
    return assinatura


def construir_signatarios_padrao(entidade, extra_emails=None):
    """Monta lista padrão de signatários com base na entidade relacionada."""
    if entidade is None:
        return []

    campos_prioritarios = (
        'beneficiario',
        'proponente',
        'credor',
        'suprido',
        'solicitante',
        'fiscal_contrato',
        'criador',
        'aprovado_por_supervisor',
        'aprovado_por_ordenador',
        'aprovado_por_conselho',
    )

    emails = []
    for campo in campos_prioritarios:
        candidato = getattr(entidade, campo, None)
        email = getattr(candidato, 'email', None) if candidato else None
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
        signatarios.append({'email': email, 'action': 'SIGN'})

    return signatarios


def enviar_para_assinatura(entidade, tipo_documento, nome_doc, signatarios, doc_type=None, pdf_bytes=None, **kwargs):
    """Gera e envia um documento para assinatura no Autentique."""
    from processos.services.integracoes.autentique import enviar_documento_para_assinatura
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
            raise ValueError('doc_type é obrigatório quando pdf_bytes não for informado.')
        pdf_bytes = gerar_documento_bytes(doc_type, entidade, **kwargs)

    resultado = enviar_documento_para_assinatura(pdf_bytes, nome_doc, signatarios)

    return AssinaturaAutentique.objects.create(
        content_type=ct,
        object_id=entidade.pk,
        tipo_documento=tipo_documento,
        autentique_id=resultado['id'],
        autentique_url=resultado['url'],
        dados_signatarios=resultado['signers_data'],
        status='PENDENTE',
    )


def disparar_assinatura_rascunho(assinatura, signatarios, nome_doc=None):
    """Dispara um rascunho de assinatura já anexado para o Autentique."""
    from processos.services.integracoes.autentique import enviar_documento_para_assinatura

    if not assinatura.arquivo:
        raise ValueError('Nenhum arquivo de rascunho encontrado para este documento.')

    with assinatura.arquivo.open('rb') as f:
        pdf_bytes = f.read()

    nome = nome_doc or f'{assinatura.tipo_documento}_{assinatura.id}'
    resultado = enviar_documento_para_assinatura(pdf_bytes, nome, signatarios)

    assinatura.autentique_id = resultado['id']
    assinatura.autentique_url = resultado['url']
    assinatura.dados_signatarios = resultado['signers_data']
    assinatura.status = 'PENDENTE'
    assinatura.save()
    return assinatura


def disparar_assinatura_rascunho_com_signatarios(assinatura):
    """Resolve signatários padrão e dispara um rascunho de assinatura."""
    entidade = assinatura.entidade_relacionada
    if entidade is None:
        raise AssinaturaSignatariosError(
            "Não foi possível resolver a entidade relacionada para assinatura."
        )

    signatarios = construir_signatarios_padrao(entidade)
    if not signatarios:
        raise AssinaturaSignatariosError(
            "Não foi possível determinar signatários para o documento informado."
        )

    nome_doc = f'{assinatura.tipo_documento}_{assinatura.id}'
    return disparar_assinatura_rascunho(assinatura, signatarios, nome_doc=nome_doc)


def sincronizar_assinatura(assinatura):
    """Sincroniza assinatura no Autentique e atualiza arquivo assinado."""
    from processos.services.integracoes.autentique import verificar_e_baixar_documento

    if assinatura.status == 'ASSINADO':
        return 'already_signed'

    resultado = verificar_e_baixar_documento(assinatura.autentique_id)
    if not resultado['assinado']:
        return 'pending'

    nome_arquivo = f'{assinatura.tipo_documento}_Assinado_{assinatura.id}.pdf'
    assinatura.arquivo_assinado.save(nome_arquivo, ContentFile(resultado['pdf_bytes']), save=False)
    assinatura.status = 'ASSINADO'
    assinatura.save()
    return 'signed'


__all__ = [
    'construir_signatarios_padrao',
    'criar_assinatura_rascunho',
    'disparar_assinatura_rascunho',
    'disparar_assinatura_rascunho_com_signatarios',
    'enviar_para_assinatura',
    'gerar_documento_bytes',
    'gerar_resposta_pdf',
    'montar_resposta_pdf',
    'sincronizar_assinatura',
]