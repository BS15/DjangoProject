"""Painel GET de liquidações (ateste de notas fiscais)."""

from django.contrib.auth.decorators import permission_required

from .....filters import DocumentoFiscalFilter
from .....models import DocumentoFiscal
from ....shared import render_filtered_list


@permission_required("processos.acesso_backoffice", raise_exception=True)
def painel_liquidacoes_view(request):
    queryset_base = DocumentoFiscal.objects.select_related(
        "processo", "nome_emitente", "fiscal_contrato"
    ).all().order_by("-id")

    is_manager = request.user.groups.filter(name__in=["Ordenadores de Despesa", "Gestores"]).exists()
    if not is_manager:
        is_fiscal = request.user.groups.filter(name="FISCAL DE CONTRATO").exists()
        if is_fiscal:
            queryset_base = queryset_base.filter(fiscal_contrato=request.user)
        else:
            queryset_base = queryset_base.none()

    return render_filtered_list(
        request,
        queryset=queryset_base,
        filter_class=DocumentoFiscalFilter,
        template_name="fluxo/painel_liquidacoes.html",
        items_key="notas",
        extra_context={
            "pode_interagir": request.user.has_perm("processos.pode_atestar_liquidacao"),
        },
    )


__all__ = ["painel_liquidacoes_view"]
