"""Views do painel de liquidacoes."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from ..filters import DocumentoFiscalFilter
from ..models import DocumentoFiscal


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

    meu_filtro = DocumentoFiscalFilter(request.GET, queryset=queryset_base)

    context = {
        "meu_filtro": meu_filtro,
        "notas": meu_filtro.qs,
        "pode_interagir": request.user.has_perm("processos.pode_atestar_liquidacao"),
    }
    return render(request, "fluxo/painel_liquidacoes.html", context)


@permission_required("processos.pode_atestar_liquidacao", raise_exception=True)
def alternar_ateste_nota(request, pk):
    """Permite atestar ou remover o ateste de uma nota diretamente pelo painel."""
    if request.method == "POST":
        if not request.user.has_perm("processos.pode_atestar_liquidacao"):
            raise PermissionDenied
        nota = get_object_or_404(DocumentoFiscal, id=pk)

        nota.atestada = not nota.atestada
        nota.save()

        if nota.atestada:
            messages.success(request, f"Nota Fiscal #{nota.numero_nota_fiscal} ATESTADA com sucesso!")
        else:
            messages.warning(request, f"Ateste da Nota Fiscal #{nota.numero_nota_fiscal} foi revogado.")

    return redirect("painel_liquidacoes")
