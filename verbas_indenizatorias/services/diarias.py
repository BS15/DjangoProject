"""Operacoes documentais especificas de diarias."""

from commons.shared.document_services import obter_ou_criar_tipo_documento, obter_proxima_ordem_documento
from django.core.files.base import ContentFile
from fluxo.services.shared import criar_assinatura_rascunho, gerar_documento_bytes
from verbas_indenizatorias.models import DocumentoDiaria


def gerar_e_anexar_scd_diaria(diaria, criador):
    """Gera SCD da diaria, anexa DocumentoDiaria e cria rascunho de assinatura."""
    pdf_bytes = gerar_documento_bytes("scd", diaria)

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
    )
