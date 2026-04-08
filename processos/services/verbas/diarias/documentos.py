"""Operações documentais específicas de diárias."""

from django.core.files.base import ContentFile
from django.db.models import Max

from ...shared.documentos import criar_assinatura_rascunho, gerar_documento_bytes


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
        arquivo=ContentFile(pdf_bytes, name=f'SCD_{diaria.id}.pdf'),
        tipo=tipo_scd,
        ordem=proxima_ordem,
    )
    return criar_assinatura_rascunho(
        entidade=diaria,
        tipo_documento='SCD',
        criador=criador,
        pdf_bytes=pdf_bytes,
        nome_arquivo=f'SCD_{diaria.id}.pdf',
    )


__all__ = ['gerar_e_anexar_scd_diaria']