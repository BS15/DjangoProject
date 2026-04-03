"""Views do fluxo de pré-pagamento: criação, edição, empenho e avanço de processos."""

from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from ..filters import AEmpenharFilter
from ..forms import DocumentoFormSet, PendenciaFormSet, ProcessoForm
from ..models import Processo, StatusChoicesProcesso, TiposDeDocumento, DocumentoProcesso
from ..validators import STATUS_BLOQUEADOS_TOTAL, STATUS_SOMENTE_DOCUMENTOS


def _obter_campo_ordenacao(request, campos_permitidos, default_ordem="id", default_direcao="desc"):
    """Extrai e formata o campo de ordenação a partir dos parâmetros GET.

    Garante que apenas colunas mapeadas em `campos_permitidos` sejam usadas,
    prevenindo sortings arbitrários. Retorna a string de campo pronta para
    `queryset.order_by()`, com prefixo `-` quando descendente.
    """
    ordem = request.GET.get("ordem", default_ordem)
    direcao = request.GET.get("direcao", default_direcao)
    order_field = campos_permitidos.get(ordem, campos_permitidos.get(default_ordem, "id"))
    return f"-{order_field}" if direcao == "desc" else order_field


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


def _registrar_empenho_e_anexar_siscac(processo, n_empenho, data_empenho_str, siscac_file):
    """Grava nota de empenho e data no processo e, opcionalmente, anexa o SISCAC.

    Quando `siscac_file` é fornecido, insere o arquivo como tipo
    "DOCUMENTOS ORÇAMENTÁRIOS" na posição 1, incrementando as ordens dos demais
    via expressão `F()` (1 query no banco). Encerra sempre com `.save()` nos
    campos `n_nota_empenho` e `data_empenho`.
    """
    processo.n_nota_empenho = n_empenho
    processo.data_empenho = datetime.strptime(data_empenho_str, "%Y-%m-%d").date()

    if siscac_file:
        tipo_doc, _ = TiposDeDocumento.objects.get_or_create(
            tipo_de_documento__iexact="DOCUMENTOS ORÇAMENTÁRIOS",
            defaults={"tipo_de_documento": "DOCUMENTOS ORÇAMENTÁRIOS"},
        )
        processo.documentos.all().update(ordem=F("ordem") + 1)
        DocumentoProcesso.objects.create(
            processo=processo, arquivo=siscac_file, tipo=tipo_doc, ordem=1
        )

    processo.save(update_fields=["n_nota_empenho", "data_empenho"])


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

    if processo.tipo_pagamento and processo.tipo_pagamento.tipo_de_pagamento.upper() == "VERBAS INDENIZATÓRIAS":
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
        processo.n_nota_empenho = None
        processo.data_empenho = None
        processo.ano_exercicio = None


def home_page(request):
    """Lista todos os processos com filtro e ordenação via parâmetros GET.

    Parâmetros GET reconhecidos: `ordem` (coluna) e `direcao` (`asc`/`desc`).
    Delega a filtragem ao `ProcessoFilter`.
    """
    from ..filters import ProcessoFilter

    order_field = _obter_campo_ordenacao(
        request,
        campos_permitidos={
            "id": "id",
            "credor": "credor__nome",
            "data_empenho": "data_empenho",
            "status": "status__status_choice",
            "tipo_pagamento": "tipo_pagamento__tipo_de_pagamento",
            "valor_liquido": "valor_liquido",
        },
    )

    processos_base = Processo.objects.all().order_by(order_field)
    meu_filtro = ProcessoFilter(request.GET, queryset=processos_base)

    context = {
        "lista_processos": meu_filtro.qs,
        "meu_filtro": meu_filtro,
        "ordem": request.GET.get("ordem", "id"),
        "direcao": request.GET.get("direcao", "desc"),
    }
    return render(request, "home.html", context)


def _obter_estatisticas_boletos(processo):
    """Retorna um dict com contagem de boletos e lista de códigos de barras presentes.

    Chaves: `boleto_docs_count`, `boleto_barcodes_list`, `boleto_barcodes_count`.
    Pronto para ser desempacotado no contexto da view com `**`.
    """
    boleto_docs_qs = processo.documentos.select_related("tipo").filter(
        tipo__tipo_de_documento__icontains="boleto"
    )
    boleto_barcodes_list = [doc.codigo_barras for doc in boleto_docs_qs if doc.codigo_barras]
    return {
        "boleto_docs_count": boleto_docs_qs.count(),
        "boleto_barcodes_list": boleto_barcodes_list,
        "boleto_barcodes_count": len(boleto_barcodes_list),
    }


def _verificar_documento_orcamentario(documento_formset, is_extra, trigger_a_empenhar):
    """Retorna `True` se a regra de documento orçamentário estiver satisfeita.

    Processos extraorçamentários ou marcados `A EMPENHAR` estão isentos da regra.
    Para os demais, pelo menos um formulário do formset deve ter tipo cujo nome
    contenha "orçament" e não estar marcado para deleção.
    """
    if is_extra or trigger_a_empenhar:
        return True
    return any(
        f.cleaned_data
        and not f.cleaned_data.get("DELETE", False)
        and f.cleaned_data.get("tipo")
        and "orçament" in f.cleaned_data["tipo"].tipo_de_documento.lower()
        for f in documento_formset.forms
    )


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

    if trigger_a_empenhar or is_extra:
        processo.n_nota_empenho = None
        processo.data_empenho = None
        processo.ano_exercicio = None


@permission_required("processos.acesso_backoffice", raise_exception=True)
def add_process_view(request):
    """Cria um novo processo de pagamento.

    Em POST válido, persiste capa + documentos + pendências em transação atômica
    e define o status inicial: `A EMPENHAR` (via checkbox) ou
    `A PAGAR - PENDENTE AUTORIZAÇÃO`. Processos padrão (não extraorçamentários e
    não "a empenhar") exigem ao menos um documento orçamentário no formset.

    Redireciona para fiscais se `btn_goto_fiscais` estiver presente, para `next`
    se seguro, ou para a tela de edição. Qualquer falha renderiza o formulário
    com os erros preservados (single exit point).
    """
    post_data = request.POST if request.method == "POST" else None
    files_data = request.FILES if request.method == "POST" else None

    processo_form = ProcessoForm(post_data, prefix="processo")
    documento_formset = DocumentoFormSet(post_data, files_data, prefix="documento")
    pendencia_formset = PendenciaFormSet(post_data, prefix="pendencia")
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER", "")

    if request.method == "POST":
        trigger_a_empenhar = request.POST.get("trigger_a_empenhar") == "on"

        if processo_form.is_valid() and documento_formset.is_valid() and pendencia_formset.is_valid():
            is_extra = processo_form.cleaned_data.get("extraorcamentario")

            if not _verificar_documento_orcamentario(documento_formset, is_extra, trigger_a_empenhar):
                messages.error(
                    request,
                    "É necessário anexar um Documento Orçamentário para prosseguir. "
                    "Se o processo for Extraorçamentário ou \"A Empenhar\", selecione a opção correspondente.",
                )
            else:
                try:
                    def mutator(processo_instancia):
                        _configurar_status_novo_processo(processo_instancia, trigger_a_empenhar, is_extra)

                    processo = _salvar_processo_completo(
                        processo_form,
                        mutator_func=mutator,
                        docs=documento_formset,
                        pends=pendencia_formset,
                    )

                    messages.success(request, f"Processo #{processo.id} inserido com sucesso!")
                    if request.POST.get("btn_goto_fiscais"):
                        return redirect("documentos_fiscais", pk=processo.id)
                    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                        return redirect(next_url)
                    return redirect("editar_processo", pk=processo.id)
                except Exception as e:
                    print(f"🛑 Erro CRÍTICO de Banco de Dados ao salvar: {e}", flush=True)
                    messages.error(request, "Ocorreu um erro interno ao salvar no banco de dados.")
        else:
            messages.error(request, "Verifique os erros no formulário (Documentos ou Capa).")

    return render(
        request,
        "fluxo/add_process.html",
        {
            "processo_form": processo_form,
            "documento_formset": documento_formset,
            "pendencia_formset": pendencia_formset,
            "next_url": next_url,
        },
    )


@permission_required("processos.acesso_backoffice", raise_exception=True)
def editar_processo(request, pk):
    """Edita um processo existente respeitando as travas do workflow.

    Modos de operação (determinados por `_validar_regras_edicao_processo`):
    - **Bloqueado**: redireciona para home sem renderizar o formulário.
    - **Verbas indenizatórias**: delega ao editor específico.
    - **Somente documentos** (`STATUS_SOMENTE_DOCUMENTOS`): apenas o
      `DocumentoFormSet` é vinculado ao POST; capa e pendências carregam
      somente da instância.
    - **Edição completa**: todos os formsets vinculados ao POST; suporta a
      confirmação de transição para extraorçamentário via checkbox.

    Segue o padrão Single Exit Point — erros de validação ou falhas de banco
    caem no único `render()` ao final, com os formulários e erros intactos.
    """
    processo = get_object_or_404(Processo, id=pk)
    status_inicial = processo.status.status_choice.upper() if processo.status else ""
    redirecionamento, somente_documentos = _validar_regras_edicao_processo(request, processo, status_inicial)
    if redirecionamento:
        return redirecionamento

    post_data = request.POST if request.method == "POST" else None
    files_data = request.FILES if request.method == "POST" else None
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER", "")

    documento_formset = DocumentoFormSet(post_data, files_data, instance=processo, prefix="documento")
    processo_post_data = post_data if not somente_documentos else None
    processo_form = ProcessoForm(processo_post_data, instance=processo, prefix="processo")
    pendencia_formset = PendenciaFormSet(processo_post_data, instance=processo, prefix="pendencia")

    if request.method == "POST":
        if somente_documentos:
            if documento_formset.is_valid():
                try:
                    with transaction.atomic():
                        documento_formset.save()
                    messages.success(request, f"Documentos do Processo #{pk} atualizados com sucesso!")
                    return redirect(next_url) if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}) else redirect("editar_processo", pk=pk)
                except Exception as e:
                    print(f"🛑 Erro ao atualizar documentos: {e}")
                    messages.error(request, "Erro interno ao salvar os documentos.")
            else:
                messages.error(request, "Verifique os erros nos documentos.")
        else:
            if processo_form.is_valid() and documento_formset.is_valid() and pendencia_formset.is_valid():
                confirmar_extra = request.POST.get("confirmar_extra_orcamentario") == "on"
                try:
                    def _mutator(proc):
                        _aplicar_confirmacao_extra_orcamentario(proc, confirmar_extra, status_inicial)

                    processo_saved = _salvar_processo_completo(
                        processo_form,
                        mutator_func=_mutator,
                        docs=documento_formset,
                        pends=pendencia_formset,
                    )

                    messages.success(request, f"Processo #{processo_saved.id} atualizado com sucesso!")
                    return redirect(next_url) if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}) else redirect("editar_processo", pk=processo_saved.id)
                except Exception as e:
                    print(f"🛑 Erro ao atualizar no banco: {e}")
                    messages.error(request, "Erro interno ao salvar as alterações.")
            else:
                messages.error(request, "Verifique os erros no formulário.")

    context = {
        "processo_form": processo_form,
        "documento_formset": documento_formset,
        "pendencia_formset": pendencia_formset,
        "processo": processo,
        "status_inicial": status_inicial,
        "somente_documentos": somente_documentos,
        "aguardando_liquidacao": status_inicial.startswith("AGUARDANDO LIQUIDAÇÃO"),
        "documentos_fiscais_url": reverse("documentos_fiscais", kwargs={"pk": processo.id}),
        "next_url": next_url,
        **_obter_estatisticas_boletos(processo),
    }

    return render(request, "fluxo/editar_processo.html", context)


@require_GET
@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def a_empenhar_view(request):
    """Exibe a fila filtrável/ordenável dos processos pendentes de empenho."""
    order_field = _obter_campo_ordenacao(
        request,
        campos_permitidos={
            "id": "id",
            "credor": "credor__nome",
            "valor_liquido": "valor_liquido",
            "data_vencimento": "data_vencimento",
            "tipo_pagamento": "tipo_pagamento__tipo_de_pagamento",
        },
        default_ordem="data_vencimento",
        default_direcao="asc",
    )

    processos_base = Processo.objects.filter(status__status_choice__iexact="A EMPENHAR").select_related(
        "credor", "status", "tipo_pagamento"
    )
    meu_filtro = AEmpenharFilter(request.GET, queryset=processos_base)

    context = {
        "processos": meu_filtro.qs.order_by(order_field, "-id"),
        "meu_filtro": meu_filtro,
        "ordem": request.GET.get("ordem", "data_vencimento"),
        "direcao": request.GET.get("direcao", "asc"),
        "pode_interagir": True,
    }
    return render(request, "fluxo/a_empenhar.html", context)


@require_POST
@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def registrar_empenho_action(request):
    """Processa a submissão do modal de empenho e avança o processo para `AGUARDANDO LIQUIDAÇÃO`.

    Endpoint RPC-style dedicado exclusivamente ao POST do modal da fila de empenho.
    Delega a persistência a `_registrar_empenho_e_anexar_siscac` e sempre redireciona
    de volta para `a_empenhar`, com ou sem erro.
    """
    processo_id = request.POST.get("processo_id")
    n_nota_empenho = request.POST.get("n_nota_empenho")
    data_empenho_str = request.POST.get("data_empenho")
    siscac_file = request.FILES.get("siscac_file")

    if not (processo_id and n_nota_empenho and data_empenho_str):
        messages.error(request, "Por favor, preencha o número e a data da nota de empenho para avançar.")
        return redirect("a_empenhar")

    try:
        with transaction.atomic():
            processo = Processo.objects.get(id=processo_id)
            _registrar_empenho_e_anexar_siscac(processo, n_nota_empenho, data_empenho_str, siscac_file)
            try:
                processo.avancar_status("AGUARDANDO LIQUIDAÇÃO", usuario=request.user)
            except ValidationError as ve:
                raise ValueError(str(ve))

        messages.success(
            request,
            f"Empenho registrado com sucesso! Processo #{processo.id} avançou para Aguardando Liquidação.",
        )
    except Processo.DoesNotExist:
        messages.error(request, "Processo não encontrado.")
    except Exception as e:
        messages.error(request, f"Erro inesperado ao salvar empenho: {str(e)}")

    return redirect("a_empenhar")


@require_POST
@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def avancar_para_pagamento_view(request, pk):
    """Avança um processo de `AGUARDANDO LIQUIDAÇÃO` para `A PAGAR - PENDENTE AUTORIZAÇÃO`.

    Valida o status atual e delega a transição ao método `avancar_status` do modelo
    dentro de transação atômica. Sempre redireciona para a tela de edição do processo,
    com ou sem erro.
    """
    processo = get_object_or_404(Processo, id=pk)
    status_atual = processo.status.status_choice.upper() if processo.status else ""

    if not status_atual.startswith("AGUARDANDO LIQUIDAÇÃO"):
        messages.error(
            request,
            f'O processo #{pk} não está em status "Aguardando Liquidação" '
            f'(status atual: "{processo.status}"). Ação não permitida.',
        )
        return redirect("editar_processo", pk=pk)

    try:
        with transaction.atomic():
            processo.avancar_status("A PAGAR - PENDENTE AUTORIZAÇÃO", usuario=request.user)

        messages.success(request, f'Processo #{pk} avançado com sucesso para "A Pagar - Pendente Autorização".')
    except ValidationError as ve:
        for erro in ve.messages:
            messages.error(request, erro)
    except Exception as e:
        messages.error(request, f"Erro ao avançar o processo: {str(e)}")

    return redirect("editar_processo", pk=pk)


__all__ = [
    "home_page",
    "add_process_view",
    "editar_processo",
    "a_empenhar_view",
    "registrar_empenho_action",
    "avancar_para_pagamento_view",
]
