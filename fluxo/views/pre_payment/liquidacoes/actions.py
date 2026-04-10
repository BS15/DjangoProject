"""Ação POST de alternância de ateste de liquidação."""

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect

from fiscal.models import DocumentoFiscal


@permission_required("fluxo.pode_atestar_liquidacao", raise_exception=True)
def alternar_ateste_nota(request, pk):
    """Permite atestar ou remover o ateste de uma nota diretamente pelo painel."""
    if request.method == "POST":
        if not request.user.has_perm("fluxo.pode_atestar_liquidacao"):
            raise PermissionDenied
        nota = get_object_or_404(DocumentoFiscal, id=pk)

        nota.atestada = not nota.atestada
        nota.save()

        if nota.atestada:
            messages.success(request, f"Nota Fiscal #{nota.numero_nota_fiscal} ATESTADA com sucesso!")
        else:
            messages.warning(request, f"Ateste da Nota Fiscal #{nota.numero_nota_fiscal} foi revogado.")

    return redirect("painel_liquidacoes")


__all__ = ["alternar_ateste_nota"]
