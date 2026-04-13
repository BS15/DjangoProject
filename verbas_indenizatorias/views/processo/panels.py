from django.contrib.auth.decorators import permission_required
from django.shortcuts import render


@permission_required("verbas_indenizatorias.pode_visualizar_verbas", raise_exception=True)
def verbas_panel_view(request):
    return render(request, 'verbas/verbas_panel.html')
