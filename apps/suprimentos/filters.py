"""Filtros de listagem para o domínio de suprimentos de fundos."""

from apps.pagamentos.filters import BaseStyledFilterSet, date_range_filter, icontains_filter
from apps.suprimentos.models import PrestacaoContasSuprimento, StatusChoicesSuprimentoDeFundos, SuprimentoDeFundos

import django_filters


class SuprimentoPainelFilter(BaseStyledFilterSet):
    """Filtro operacional do painel de suprimentos."""

    suprido = icontains_filter(field_name="suprido__nome", label="Suprido(a)")
    lotacao = icontains_filter(field_name="lotacao", label="Lotação")
    inicio_periodo = date_range_filter(label="Início Período (De - Até)")
    status = django_filters.ModelChoiceFilter(
        field_name="status",
        queryset=StatusChoicesSuprimentoDeFundos.objects.filter(is_active=True),
        label="Status",
        empty_label="Todos",
    )

    class Meta:
        model = SuprimentoDeFundos
        fields = []


class PrestacaoSuprimentoReviewFilter(BaseStyledFilterSet):
    """Filtro operacional da fila de revisão de prestações de suprimento."""

    suprido = icontains_filter(field_name="suprimento__suprido__nome", label="Suprido(a)")
    lotacao = icontains_filter(field_name="suprimento__lotacao", label="Lotação")
    submetido_por = icontains_filter(field_name="submetido_por__username", label="Enviado por")
    submetido_em = date_range_filter(label="Enviada em (De - Até)")

    class Meta:
        model = PrestacaoContasSuprimento
        fields = []
