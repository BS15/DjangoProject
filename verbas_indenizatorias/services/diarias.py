"""Operacoes documentais especificas de diarias."""

from django.core.files.base import ContentFile
from django.db.models import Max

from fluxo.models import TiposDeDocumento
from fluxo.services.shared import criar_assinatura_rascunho, gerar_documento_bytes
from verbas_indenizatorias.models import DocumentoDiaria


def gerar_e_anexar_scd_diaria(diaria, criador):
    """Gera SCD da diaria, anexa DocumentoDiaria e cria rascunho de assinatura."""
    pdf_bytes = gerar_documento_bytes("scd", diaria)

    tipo_scd, _ = TiposDeDocumento.objects.get_or_create(
        tipo_de_documento__iexact="SOLICITACAO DE CONCESSAO DE DIARIAS (SCD)",
        defaults={"tipo_de_documento": "SOLICITACAO DE CONCESSAO DE DIARIAS (SCD)"},
    )
    proxima_ordem = (diaria.documentos.aggregate(max_ordem=Max("ordem"))["max_ordem"] or 0) + 1
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
