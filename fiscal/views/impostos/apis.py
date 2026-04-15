"""Endpoints API do domínio de retenções de impostos."""

from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST


@require_POST
@permission_required("fiscal.acesso_backoffice", raise_exception=True)
def api_processar_retencoes(request):
    """Processa upload de PDF de nota fiscal para extração de retenções."""
    if not request.FILES.get("arquivo"):
        return JsonResponse(
            {"status": "error", "message": "Requisição inválida ou arquivo ausente"},
            status=400,
        )

    return JsonResponse(
        {"status": "error", "message": "Extração por IA não disponível."},
        status=400,
    )


__all__ = ["api_processar_retencoes"]
