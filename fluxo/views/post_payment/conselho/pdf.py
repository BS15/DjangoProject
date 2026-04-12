"""PDF views da etapa de conselho fiscal."""

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404
from django.views.decorators.clickjacking import xframe_options_sameorigin

from fluxo.models import Processo
from fluxo.services.shared import gerar_resposta_pdf


__all__ = []
