import csv
import io
import random
from datetime import date, timedelta
from decimal import Decimal

from faker import Faker
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from credores.imports import (
    download_template_csv_credores,
    painel_importacao_view,
)
from fluxo.support.conta_fixa_imports import download_template_csv_contas
from ..utils import format_brl_currency
from ..models import (
    CargosFuncoes,
    CodigosImposto,
    ContasBancarias,
    Credor,
    Diaria,
    DocumentoDePagamento,
    DocumentoFiscal,
    FormasDePagamento,
    MeiosDeTransporte,
    Processo,
    RetencaoImposto,
    StatusChoicesProcesso,
    StatusChoicesRetencoes,
    StatusChoicesVerbasIndenizatorias,
    TagChoices,
    TiposDeDocumento,
    TiposDePagamento,
)

_fake_generator = Faker('pt_BR')
_MIN_FAKE_ANO_EXERCICIO = 2020

def _ensure_fake_lookup_tables():
    """Garante dados mínimos de catálogos para geração de registros fictícios."""
    for s in [
        "AGUARDANDO LIQUIDAÇÃO / ATESTE",
        "A PAGAR - PENDENTE AUTORIZAÇÃO",
        "PAGO - EM CONFERÊNCIA",
        "ARQUIVADO",
        "CANCELADO / ANULADO",
    ]:
        StatusChoicesProcesso.objects.get_or_create(status_choice=s)

    for t in ["Serviços", "Material", "Contrato", "Diárias"]:
        TagChoices.objects.get_or_create(tag_choice=t)

    for f in ["PIX", "TRANSFERÊNCIA (TED)", "REMESSA BANCÁRIA"]:
        FormasDePagamento.objects.get_or_create(forma_de_pagamento=f)

    for t in ["CONTAS FIXAS", "VERBAS INDENIZATÓRIAS", "IMPOSTOS"]:
        pass  # Exemplo de lógica adicional
