from django.db.models import Prefetch

from pagamentos.models import AssinaturaEletronica
from verbas_indenizatorias.constants import STATUS_VERBA_SOLICITADA
from verbas_indenizatorias.models import Diaria

STATUS_ASSINATURA_PENDENTE = 'PENDENTE'


def listar_diarias_pendentes_para_proponente(usuario):
    diarias = (
        Diaria.objects
        .filter(
            proponente=usuario,
            status__status_choice__iexact=STATUS_VERBA_SOLICITADA,
        )
        .select_related('beneficiario', 'status')
        .prefetch_related(
            Prefetch(
                'assinaturas_autentique',
                queryset=AssinaturaEletronica.objects.order_by('-criado_em'),
                to_attr='assinaturas_para_autorizacao',
            )
        )
        .order_by('-id')
    )

    itens_autorizacao = []
    for diaria in diarias:
        assinaturas = getattr(diaria, 'assinaturas_para_autorizacao', [])
        assinatura = next((item for item in assinaturas if item.status == STATUS_ASSINATURA_PENDENTE), None)
        itens_autorizacao.append(
            {
                'diaria': diaria,
                'autentique_url_pendente': assinatura.autentique_url if assinatura else None,
            }
        )

    return itens_autorizacao


__all__ = ['listar_diarias_pendentes_para_proponente']
