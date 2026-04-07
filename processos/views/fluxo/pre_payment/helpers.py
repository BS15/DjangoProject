"""Funções auxiliares privadas para o módulo de pré-pagamento."""

from datetime import datetime

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

from ....models import Processo, StatusChoicesProcesso, TiposDeDocumento, DocumentoDePagamento
from ....validators import STATUS_BLOQUEADOS_TOTAL, STATUS_SOMENTE_DOCUMENTOS


def _salvar_processo_completo(processo_form, mutator_func=None, **formsets):
    """Salva a capa do processo e quaisquer formsets em transação atômica.

    Aplica `mutator_func` antes do primeiro `.save()`, permitindo que regras de
    negócio (ex.: definir status) sejam injetadas sem poluir a view.
    Aceita formsets como kwargs nomeados — agnóstico ao número e tipo deles.

    Retorna a instância de `Processo` persistida.
    """
    with transaction.atomic():
        processo = processo_form.save(commit=False)

        if mutator_func:
            mutator_func(processo)

        processo.save()

        for formset in formsets.values():
            if formset:
                formset.instance = processo
                formset.save()

        return processo


def _registrar_empenho_e_anexar_siscac(processo, n_empenho, data_empenho_str, siscac_file, ano_exercicio=None):
    """Grava nota de empenho e data no processo e, opcionalmente, anexa o SISCAC.

    Quando `siscac_file` é fornecido, insere o arquivo como tipo
    "DOCUMENTOS ORÇAMENTÁRIOS" na posição 1, incrementando as ordens dos demais
    via expressão `F()` (1 query no banco). Encerra sempre com `.save()` nos
    campos `n_nota_empenho` e `data_empenho`.
    """
    data_empenho = datetime.strptime(data_empenho_str, "%Y-%m-%d").date()
    processo.registrar_documento_orcamentario(
        numero_nota_empenho=n_empenho,
        data_empenho=data_empenho,
        ano_exercicio=ano_exercicio or data_empenho.year,
    )

    if siscac_file:
        tipo_doc, _ = TiposDeDocumento.objects.get_or_create(
            tipo_de_documento__iexact="DOCUMENTOS ORÇAMENTÁRIOS",
            defaults={"tipo_de_documento": "DOCUMENTOS ORÇAMENTÁRIOS"},
        )
        processo.documentos.all().update(ordem=F("ordem") + 1)
        DocumentoDePagamento.objects.create(
            processo=processo, arquivo=siscac_file, tipo=tipo_doc, ordem=1
        )

    processo.save()


def _validar_regras_edicao_processo(request, processo, status_inicial):
    """Aplica as regras de guarda da edição e retorna `(redirect | None, somente_documentos)`.

    Possíveis saídas:
    - Status bloqueado → redireciona para home com mensagem de erro.
    - Tipo de pagamento "VERBAS INDENIZATÓRIAS" → redireciona para o editor específico.
    - Status em `STATUS_SOMENTE_DOCUMENTOS` → `somente_documentos=True`, sem redirect.
    - Demais casos → `(None, False)`, edição completa liberada.
    """
    if status_inicial in STATUS_BLOQUEADOS_TOTAL:
        messages.error(
            request,
            f'O processo #{processo.id} está em status "{processo.status}" e não pode ser editado. '
            "Alterações nesses processos devem ser tratadas pela interface de contingência.",
        )
        return redirect("home_page"), False

    if (
        getattr(processo, "tipo_pagamento_id", None)
        and processo.tipo_pagamento
        and (processo.tipo_pagamento.tipo_de_pagamento or "").upper() == "VERBAS INDENIZATÓRIAS"
    ):
        return redirect("editar_processo_verbas", pk=processo.id), False

    return None, status_inicial in STATUS_SOMENTE_DOCUMENTOS


def _aplicar_confirmacao_extra_orcamentario(processo, confirmar_extra, status_inicial):
    """Converte um processo em extraorçamentário quando o usuário confirma em `A EMPENHAR`.

    Muda o status para `A PAGAR - PENDENTE AUTORIZAÇÃO`, seta `extraorcamentario=True`
    e limpa os campos de empenho. Sem efeito para qualquer outro status.
    """
    if confirmar_extra and status_inicial == "A EMPENHAR":
        status_obj, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact="A PAGAR - PENDENTE AUTORIZAÇÃO",
            defaults={"status_choice": "A PAGAR - PENDENTE AUTORIZAÇÃO"},
        )
        processo.status = status_obj
        processo.extraorcamentario = True


def _redirect_seguro_ou_fallback(request, next_url, fallback_name, pk):
    """Redireciona para `next` quando seguro; caso contrário usa rota fallback."""
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(fallback_name, pk=pk)


def _configurar_status_novo_processo(processo, trigger_a_empenhar, is_extra):
    """Define o status inicial do processo na criação.

    Define `A EMPENHAR` ou `A PAGAR - PENDENTE AUTORIZAÇÃO` conforme a flag
    `trigger_a_empenhar`. Limpa nota/data de empenho e ano de exercício quando
    o processo ainda não passou pela fase de empenho.
    """
    nome_status = "A EMPENHAR" if trigger_a_empenhar else "A PAGAR - PENDENTE AUTORIZAÇÃO"
    status_obj, _ = StatusChoicesProcesso.objects.get_or_create(
        status_choice__iexact=nome_status, defaults={"status_choice": nome_status}
    )
    processo.status = status_obj

    # Dados de empenho agora são armazenados em DocumentoOrcamentario.
