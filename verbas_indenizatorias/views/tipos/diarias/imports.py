from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import redirect, render

from fluxo.utils import confirmar_diarias_lote, preview_diarias_lote


@permission_required("fluxo.pode_importar_diarias", raise_exception=True)
def importar_diarias_view(request):
    session_key = "importar_diarias_preview"
    context = {}

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "confirmar":
            preview_items = request.session.pop(session_key, None)
            if not isinstance(preview_items, list) or not preview_items:
                messages.error(request, "Sessao expirada ou previa nao encontrada. Por favor, importe o arquivo novamente.")
                return redirect("importar_diarias")

            resultados = confirmar_diarias_lote(preview_items, request.user)
            context["resultados"] = resultados

        elif action == "cancelar":
            request.session.pop(session_key, None)
            return redirect("importar_diarias")

        elif request.FILES.get("csv_file"):
            resultado_preview = preview_diarias_lote(request.FILES["csv_file"])
            request.session[session_key] = resultado_preview["preview"]
            context["preview"] = resultado_preview["preview"]
            context["erros_preview"] = resultado_preview["erros"]

    return render(request, "verbas/importar_diarias.html", context)
