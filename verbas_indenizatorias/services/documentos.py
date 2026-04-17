"""Serviços documentais centralizados para verbas indenizatórias: diárias, reembolsos, jetons, auxílios.

Este módulo implementa funções para geração e anexação de documentos PDF relacionados a verbas indenizatórias.
"""

from commons.shared.document_services import obter_ou_criar_tipo_documento, obter_proxima_ordem_documento
from commons.shared.pdf_response import gerar_documento_bytes
from commons.shared.signature_services import criar_assinatura_rascunho
from django.core.files.base import ContentFile
from fluxo.models import AssinaturaAutentique
from verbas_indenizatorias.pdf_generators import VERBAS_DOCUMENT_REGISTRY
from verbas_indenizatorias.models import (
    DocumentoDiaria, DocumentoReembolso, DocumentoJeton, DocumentoAuxilio,
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
        assinatura_model=AssinaturaAutentique,
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
        assinatura_model=AssinaturaAutentique,
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
        assinatura_model=AssinaturaAutentique,
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
        assinatura_model=AssinaturaAutentique,
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
        assinatura_model=AssinaturaAutentique,
    )
