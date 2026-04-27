from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import redirect, render

from .import_services import confirmar_diarias_lote_com_modo, preview_diarias_lote


@permission_required("pagamentos.pode_importar_diarias", raise_exception=True)
def importar_diarias_view(request):
    session_key = "importar_diarias_preview"
    session_mode_key = "importar_diarias_modo_assinado"
    context = {}

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "confirmar":
            preview_items = request.session.pop(session_key, None)
            modo_assinado = bool(request.session.pop(session_mode_key, False))
            if not isinstance(preview_items, list) or not preview_items:
                messages.error(request, "Sessao expirada ou previa nao encontrada. Por favor, importe o arquivo novamente.")
                return redirect("importar_diarias")

            resultados = confirmar_diarias_lote_com_modo(
                preview_items,
                request.user,
                solicitacao_assinada=modo_assinado,
            )
            context["resultados"] = resultados

        elif action == "cancelar":
            request.session.pop(session_key, None)
            request.session.pop(session_mode_key, None)
            return redirect("importar_diarias")

        elif request.FILES.get("csv_file"):
            resultado_preview = preview_diarias_lote(request.FILES["csv_file"])
            modo_assinado = request.POST.get("modo_solicitacao_assinada") == "on"
            request.session[session_key] = resultado_preview["preview"]
            request.session[session_mode_key] = modo_assinado
            context["preview"] = resultado_preview["preview"]
            context["erros_preview"] = resultado_preview["erros"]
            context["modo_solicitacao_assinada"] = modo_assinado

    if "modo_solicitacao_assinada" not in context:
        context["modo_solicitacao_assinada"] = bool(request.session.get(session_mode_key, False))

    return render(request, "verbas/importar_diarias.html", context)
