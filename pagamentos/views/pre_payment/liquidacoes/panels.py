"""Painel GET de liquidações (ateste de notas fiscais)."""

from fiscal.filters import DocumentoFiscalFilter
from fiscal.models import DocumentoFiscal
from pagamentos.views.shared import render_filtered_list


def painel_liquidacoes_view(request):
    queryset_base = DocumentoFiscal.objects.select_related(
        "processo", "nome_emitente", "liquidacao__fiscal_contrato"
    ).all().order_by("-id")

    is_backoffice = request.user.has_perm("pagamentos.operador_contas_a_pagar")
    if not is_backoffice:
        queryset_base = queryset_base.filter(liquidacao__fiscal_contrato=request.user)

    return render_filtered_list(
        request,
        queryset=queryset_base,
        filter_class=DocumentoFiscalFilter,
        template_name="pagamentos/painel_liquidacoes.html",
        items_key="notas",
        sort_fields={
            "numero_nota_fiscal": "numero_nota_fiscal",
            "processo": "processo__id",
            "credor": "processo__credor__nome",
            "valor_bruto": "valor_bruto",
            "data_emissao": "data_emissao",
        },
        default_ordem="id",
        default_direcao="desc",
        tie_breaker="-id",
        extra_context={
            "pode_interagir": True,
        },
    )


__all__ = ["painel_liquidacoes_view"]
