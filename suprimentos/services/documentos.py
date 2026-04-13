"""Serviços documentais centralizados para suprimentos de fundos.

Este módulo implementa funções para geração e anexação de recibos e documentos PDF relacionados a suprimentos de fundos.
"""

from commons.shared.document_services import obter_ou_criar_tipo_documento, obter_proxima_ordem_documento
from django.core.files.base import ContentFile
from fluxo.services.shared import criar_assinatura_rascunho, gerar_documento_bytes
from suprimentos.models import DocumentoSuprimentoDeFundos

def gerar_e_anexar_recibo_suprimento(suprimento, criador):
    """Gera recibo de suprimento, anexa DocumentoSuprimentoDeFundos e cria rascunho de assinatura."""
    pdf_bytes = gerar_documento_bytes("recibo_suprimento", suprimento)
    tipo_recibo = obter_ou_criar_tipo_documento(
        "RECIBO DE PAGAMENTO",
    )
    proxima_ordem = obter_proxima_ordem_documento(suprimento.documentos)
    DocumentoSuprimentoDeFundos.objects.create(
        suprimento=suprimento,
        arquivo=ContentFile(pdf_bytes, name=f"Recibo_Suprimento_{suprimento.id}.pdf"),
        tipo=tipo_recibo,
        ordem=proxima_ordem,
    )
    return criar_assinatura_rascunho(
        entidade=suprimento,
        tipo_documento="RECIBO DE PAGAMENTO",
        criador=criador,
        pdf_bytes=pdf_bytes,
        nome_arquivo=f"Recibo_Suprimento_{suprimento.id}.pdf",
    )
