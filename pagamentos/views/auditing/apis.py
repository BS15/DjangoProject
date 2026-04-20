"""Endpoints GET/API da trilha de auditoria."""

from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET

from pagamentos.domain_models import Processo
from ..helpers import _build_payload_documentos_processo_auditoria, _build_payload_processo_detalhes


@permission_required("pagamentos.pode_auditar_conselho", raise_exception=True)
@require_GET
@xframe_options_sameorigin
def api_documentos_processo(request, processo_id):
    """Retorna documentos e metadados correlatos de um processo para auditoria."""
    processo = get_object_or_404(Processo, id=processo_id)
    return JsonResponse(_build_payload_documentos_processo_auditoria(processo))


@require_GET
def api_processo_detalhes(request):
    """Retorna detalhes de um processo por ``id`` informado via query string."""
    if not (
        request.user.has_perm("pagamentos.pode_auditar_conselho")
        or request.user.has_perm("pagamentos.acesso_backoffice")
    ):
        raise PermissionDenied

    processo_id = request.GET.get("id", "").strip()
    if not processo_id:
        return JsonResponse({"sucesso": False, "erro": "ID do processo não informado."}, status=400)

    try:
        processo = Processo.objects.select_related(
            "credor", "forma_pagamento", "tipo_pagamento", "conta", "status", "tag"
        ).get(pk=processo_id)
    except Processo.DoesNotExist:
        return JsonResponse({"sucesso": False, "erro": f"Processo #{processo_id} não encontrado."}, status=404)
    except ValueError:
        return JsonResponse({"sucesso": False, "erro": "ID inválido."}, status=400)

    return JsonResponse(_build_payload_processo_detalhes(processo))


__all__ = ["api_documentos_processo", "api_processo_detalhes"]