"""Serviços documentais centralizados para verbas indenizatórias: diárias, reembolsos, jetons, auxílios.

Este módulo implementa funções para geração e anexação de documentos PDF relacionados a verbas indenizatórias.
"""

from commons.shared.document_services import obter_ou_criar_tipo_documento, obter_proxima_ordem_documento
from commons.shared.pdf_response import gerar_documento_bytes
from commons.shared.signature_services import criar_assinatura_rascunho
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from pagamentos.models import AssinaturaEletronica
from verbas_indenizatorias.pdf_generators import VERBAS_DOCUMENT_REGISTRY
from verbas_indenizatorias.models import (
    DocumentoDiaria, DocumentoReembolso, DocumentoJeton, DocumentoAuxilio,
)
from verbas_indenizatorias.services.prestacao import (
    obter_ou_criar_prestacao as _obter_ou_criar_prestacao,
    registrar_comprovante as _registrar_comprovante,
)


def obter_ou_criar_prestacao(diaria):
    """Obtém prestação de contas da diária, criando em estado aberto quando ausente."""
    return _obter_ou_criar_prestacao(diaria)


def registrar_comprovante_prestacao(diaria, arquivo, tipo_id):
    """Registra comprovante na prestação de contas da diária, bloqueando prestação encerrada."""
    return _registrar_comprovante(diaria, arquivo, tipo_id)


def anexar_solicitacao_assinada_diaria(diaria, arquivo):
    """Anexa solicitação assinada da diária sem criar fluxo de assinatura eletrônica."""
    if not arquivo:
        raise ValidationError("Arquivo da solicitação assinada é obrigatório.")

    tipo_scd = obter_ou_criar_tipo_documento(
        "SOLICITACAO DE CONCESSAO DE DIARIAS (SCD)",
    )
    proxima_ordem = obter_proxima_ordem_documento(diaria.documentos)
    DocumentoDiaria.objects.create(
        diaria=diaria,
        arquivo=arquivo,
        tipo=tipo_scd,
        ordem=proxima_ordem,
    )

def gerar_e_anexar_scd_diaria(diaria, criador):
    """Gera SCD da diária, anexa DocumentoDiaria e cria rascunho de assinatura."""
    pdf_bytes = gerar_documento_bytes("scd", diaria, VERBAS_DOCUMENT_REGISTRY)
    tipo_scd = obter_ou_criar_tipo_documento(
        "SOLICITACAO DE CONCESSAO DE DIARIAS (SCD)",
    )
    proxima_ordem = obter_proxima_ordem_documento(diaria.documentos)
    DocumentoDiaria.objects.create(
        diaria=diaria,
        arquivo=ContentFile(pdf_bytes, name=f"SCD_{diaria.id}.pdf"),
        tipo=tipo_scd,
        ordem=proxima_ordem,
    )
    return criar_assinatura_rascunho(
        entidade=diaria,
        tipo_documento="SCD",
        criador=criador,
        pdf_bytes=pdf_bytes,
        nome_arquivo=f"SCD_{diaria.id}.pdf",
        assinatura_model=AssinaturaEletronica,
    )

def gerar_e_anexar_pcd_diaria(diaria, criador):
    """Gera PCD da diária, anexa DocumentoDiaria e cria rascunho de assinatura."""
    pdf_bytes = gerar_documento_bytes("pcd", diaria, VERBAS_DOCUMENT_REGISTRY)
    tipo_pcd = obter_ou_criar_tipo_documento(
        "PROPOSTA DE CONCESSÃO DE DIÁRIAS (PCD)",
    )
    proxima_ordem = obter_proxima_ordem_documento(diaria.documentos)
    DocumentoDiaria.objects.create(
        diaria=diaria,
        arquivo=ContentFile(pdf_bytes, name=f"PCD_{diaria.id}.pdf"),
        tipo=tipo_pcd,
        ordem=proxima_ordem,
    )
    return criar_assinatura_rascunho(
        entidade=diaria,
        tipo_documento="PCD",
        criador=criador,
        pdf_bytes=pdf_bytes,
        nome_arquivo=f"PCD_{diaria.id}.pdf",
        assinatura_model=AssinaturaEletronica,
    )

def gerar_e_anexar_termo_prestacao_diaria(diaria, criador):
    """Gera Termo de Prestação de Contas da diária, anexa DocumentoDiaria e cria rascunho de assinatura."""
    pdf_bytes = gerar_documento_bytes("termo_prestacao_contas", diaria, VERBAS_DOCUMENT_REGISTRY)
    tipo_termo = obter_ou_criar_tipo_documento(
        "TERMO DE PRESTAÇÃO DE CONTAS",
    )
    proxima_ordem = obter_proxima_ordem_documento(diaria.documentos)
    DocumentoDiaria.objects.create(
        diaria=diaria,
        arquivo=ContentFile(pdf_bytes, name=f"Termo_Prestacao_Contas_{diaria.id}.pdf"),
        tipo=tipo_termo,
        ordem=proxima_ordem,
    )
    return criar_assinatura_rascunho(
        entidade=diaria,
        tipo_documento="TERMO DE PRESTAÇÃO DE CONTAS",
        criador=criador,
        pdf_bytes=pdf_bytes,
        nome_arquivo=f"Termo_Prestacao_Contas_{diaria.id}.pdf",
        assinatura_model=AssinaturaEletronica,
    )


def gerar_e_anexar_recibo_reembolso(reembolso, criador):
    """Gera requerimento de reembolso, anexa DocumentoReembolso e cria rascunho de assinatura."""
    pdf_bytes = gerar_documento_bytes("recibo_reembolso", reembolso, VERBAS_DOCUMENT_REGISTRY)
    tipo_recibo = obter_ou_criar_tipo_documento(
        "REQUERIMENTO DE REEMBOLSO DE COMBUSTÍVEL",
    )
    proxima_ordem = obter_proxima_ordem_documento(reembolso.documentos)
    DocumentoReembolso.objects.create(
        reembolso=reembolso,
        arquivo=ContentFile(pdf_bytes, name=f"Requerimento_Reembolso_{reembolso.id}.pdf"),
        tipo=tipo_recibo,
        ordem=proxima_ordem,
    )
    return criar_assinatura_rascunho(
        entidade=reembolso,
        tipo_documento="REQUERIMENTO DE REEMBOLSO DE COMBUSTÍVEL",
        criador=criador,
        pdf_bytes=pdf_bytes,
        nome_arquivo=f"Requerimento_Reembolso_{reembolso.id}.pdf",
        assinatura_model=AssinaturaEletronica,
    )

def gerar_e_anexar_recibo_jeton(jeton, criador):
    """Gera recibo de jeton, anexa DocumentoJeton e cria rascunho de assinatura."""
    pdf_bytes = gerar_documento_bytes("recibo_jeton", jeton, VERBAS_DOCUMENT_REGISTRY)
    tipo_recibo = obter_ou_criar_tipo_documento(
        "RECIBO DE PAGAMENTO",
    )
    proxima_ordem = obter_proxima_ordem_documento(jeton.documentos)
    DocumentoJeton.objects.create(
        jeton=jeton,
        arquivo=ContentFile(pdf_bytes, name=f"Recibo_Jeton_{jeton.id}.pdf"),
        tipo=tipo_recibo,
        ordem=proxima_ordem,
    )
    return criar_assinatura_rascunho(
        entidade=jeton,
        tipo_documento="RECIBO DE PAGAMENTO",
        criador=criador,
        pdf_bytes=pdf_bytes,
        nome_arquivo=f"Recibo_Jeton_{jeton.id}.pdf",
        assinatura_model=AssinaturaEletronica,
    )

def gerar_e_anexar_recibo_auxilio(auxilio, criador):
    """Gera recibo de auxílio, anexa DocumentoAuxilio e cria rascunho de assinatura."""
    pdf_bytes = gerar_documento_bytes("recibo_auxilio", auxilio, VERBAS_DOCUMENT_REGISTRY)
    tipo_recibo = obter_ou_criar_tipo_documento(
        "RECIBO DE PAGAMENTO",
    )
    proxima_ordem = obter_proxima_ordem_documento(auxilio.documentos)
    DocumentoAuxilio.objects.create(
        auxilio=auxilio,
        arquivo=ContentFile(pdf_bytes, name=f"Recibo_Auxilio_{auxilio.id}.pdf"),
        tipo=tipo_recibo,
        ordem=proxima_ordem,
    )
    return criar_assinatura_rascunho(
        entidade=auxilio,
        tipo_documento="RECIBO DE PAGAMENTO",
        criador=criador,
        pdf_bytes=pdf_bytes,
        nome_arquivo=f"Recibo_Auxilio_{auxilio.id}.pdf",
        assinatura_model=AssinaturaEletronica,
    )
