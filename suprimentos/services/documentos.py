"""Serviços documentais centralizados para suprimentos de fundos.

Este módulo implementa funções para geração e anexação de recibos e documentos PDF relacionados a suprimentos de fundos.
"""

from commons.shared.document_services import obter_ou_criar_tipo_documento, obter_proxima_ordem_documento
from commons.shared.pdf_response import gerar_documento_bytes
from commons.shared.signature_services import criar_assinatura_rascunho
from django.core.files.base import ContentFile
from fluxo.models import AssinaturaAutentique
from suprimentos.pdf_generators import SUPRIMENTOS_DOCUMENT_REGISTRY
from suprimentos.models import DocumentoSuprimentoDeFundos

def gerar_e_anexar_recibo_suprimento(suprimento, criador):
    """Gera recibo de suprimento, anexa DocumentoSuprimentoDeFundos e cria rascunho de assinatura."""
    pdf_bytes = gerar_documento_bytes("recibo_suprimento", suprimento, SUPRIMENTOS_DOCUMENT_REGISTRY)
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
        assinatura_model=AssinaturaAutentique,
    )
