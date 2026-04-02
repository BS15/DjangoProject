"""Views do fluxo de PRE-PAGAMENTO."""

from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from ..filters import AEmpenharFilter
from ..forms import DocumentoFormSet, PendenciaFormSet, ProcessoForm
from ..models import Processo, StatusChoicesProcesso, TiposDeDocumento, DocumentoProcesso
from ..validators import STATUS_BLOQUEADOS_TOTAL, STATUS_SOMENTE_DOCUMENTOS


def _salvar_processo_completo(processo_form, documento_formset, pendencia_formset, mutator_func=None):
    """Executa persistência atômica da capa do processo e seus formsets.

    Args:
        processo_form: Instância de ProcessoForm válida.
        documento_formset: FormSet de documentos válido.
        pendencia_formset: FormSet de pendências válido.
        mutator_func: Função opcional que recebe a instância de Processo ainda
            não persistida e aplica regras de negócio antes do `save()`.

    Returns:
        Processo: Instância persistida após salvar capa e formsets.
    """
    with transaction.atomic():
        processo = processo_form.save(commit=False)

        if mutator_func:
            mutator_func(processo)

        processo.save()

        documento_formset.instance = processo
        pendencia_formset.instance = processo

        documento_formset.save()
        pendencia_formset.save()

        return processo


def _validar_regras_edicao_processo(request, processo, status_inicial):
    """Centraliza regras de bloqueio/redirecionamento da edição.

    Returns:
        tuple[HttpResponseRedirect | None, bool]:
            - Redirecionamento quando houver bloqueio/regra especial.
            - Flag `somente_documentos` para controlar o modo de edição.
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
    """Aplica transição para extraorçamentário quando confirmado em `A EMPENHAR`."""
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
    """Renderiza a home com listagem, filtro e ordenação de processos.

    A view aceita parâmetros GET para ordenação (`ordem`, `direcao`) e
    reutiliza `ProcessoFilter` para os filtros da listagem principal.

    Args:
        request: Requisição HTTP atual.

    Returns:
        HttpResponse: Página `home.html` com processos filtrados/ordenados e
        metadados de ordenação ativos no contexto.
    """
    ORDER_FIELDS = {
        "id": "id",
        "credor": "credor__nome",
        "data_empenho": "data_empenho",
        "status": "status__status_choice",
        "tipo_pagamento": "tipo_pagamento__tipo_de_pagamento",
        "valor_liquido": "valor_liquido",
    }
    ordem = request.GET.get("ordem", "id")
    direcao = request.GET.get("direcao", "desc")

    order_field = ORDER_FIELDS.get(ordem, "id")
    if direcao == "desc":
        order_field = f"-{order_field}"

    from ..filters import ProcessoFilter

    processos_base = Processo.objects.all().order_by(order_field)
    meu_filtro = ProcessoFilter(request.GET, queryset=processos_base)
    processos_filtrados = meu_filtro.qs

    context = {
        "lista_processos": processos_filtrados,
        "meu_filtro": meu_filtro,
        "ordem": ordem,
        "direcao": direcao,
    }
    return render(request, "home.html", context)


def _obter_estatisticas_boletos(processo):
    """Consulta documentos do processo e retorna contagem e códigos de barras de boletos."""
    boleto_docs_qs = processo.documentos.select_related("tipo").filter(
        tipo__tipo_de_documento__icontains="boleto"
    )
    boleto_barcodes_list = [doc.codigo_barras for doc in boleto_docs_qs if doc.codigo_barras]
    return {
        "boleto_docs_count": boleto_docs_qs.count(),
        "boleto_barcodes_list": boleto_barcodes_list,
        "boleto_barcodes_count": len(boleto_barcodes_list),
    }


def _configurar_status_novo_processo(processo, trigger_a_empenhar, is_extra):
    """Define o status inicial do processo e limpa dados de empenho se necessário."""
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
    """Cria um novo processo no fluxo de pré-pagamento.

    Fluxos suportados:
    1. Criação efetiva do processo com documentos e pendências.
    2. Definição inicial de status conforme regra:
       - `A EMPENHAR` quando marcado para empenho posterior.
       - `A PAGAR - PENDENTE AUTORIZAÇÃO` para casos padrão/extraorçamentários.

    Regras relevantes:
    - Para processo não extraorçamentário e não "a empenhar", exige ao menos
      um documento orçamentário no formset.
    - Persistência ocorre em transação atômica (capa + documentos + pendências).
    - Suporta redirecionamento seguro por `next`.

    Args:
        request: Requisição HTTP GET/POST.

    Returns:
        HttpResponse ou HttpResponseRedirect:
        - Renderização de formulário (GET ou erro de validação).
        - Redirecionamento para edição do processo ou tela de fiscais, em sucesso.
    """
    if request.method == "POST":
        trigger_a_empenhar = request.POST.get("trigger_a_empenhar") == "on"

        processo_form = ProcessoForm(request.POST, prefix="processo")
        documento_formset = DocumentoFormSet(request.POST, request.FILES, prefix="documento")
        pendencia_formset = PendenciaFormSet(request.POST, prefix="pendencia")

        if processo_form.is_valid() and documento_formset.is_valid() and pendencia_formset.is_valid():
            is_extra = processo_form.cleaned_data.get("extraorcamentario")

            if not is_extra and not trigger_a_empenhar:
                has_orcamentario = any(
                    f.cleaned_data
                    and not f.cleaned_data.get("DELETE", False)
                    and f.cleaned_data.get("tipo")
                    and "orçament" in f.cleaned_data["tipo"].tipo_de_documento.lower()
                    for f in documento_formset.forms
                )
                if not has_orcamentario:
                    messages.error(
                        request,
                        "É necessário anexar um Documento Orçamentário para prosseguir. "
                        "Se o processo for Extraorçamentário ou \"A Empenhar\", selecione a opção correspondente.",
                    )
                    return render(
                        request,
                        "fluxo/add_process.html",
                        {
                            "processo_form": processo_form,
                            "documento_formset": documento_formset,
                            "pendencia_formset": pendencia_formset,
                        },
                    )

            try:
                def mutator(processo_instancia):
                    _configurar_status_novo_processo(processo_instancia, trigger_a_empenhar, is_extra)

                processo = _salvar_processo_completo(
                    processo_form,
                    documento_formset,
                    pendencia_formset,
                    mutator_func=mutator,
                )

                messages.success(request, f"Processo #{processo.id} inserido com sucesso!")
                if request.POST.get("btn_goto_fiscais"):
                    return redirect("documentos_fiscais", pk=processo.id)
                next_url = request.POST.get("next", "")
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
                "next_url": request.POST.get("next", ""),
            },
        )

    processo_form = ProcessoForm(prefix="processo")
    documento_formset = DocumentoFormSet(prefix="documento")
    pendencia_formset = PendenciaFormSet(prefix="pendencia")
    next_url = request.META.get("HTTP_REFERER", "")

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
    """Edita processo existente com regras por estágio de workflow.

    Comportamento por status:
    - Status totalmente bloqueados: impede edição e redireciona para home.
    - Processos de verbas indenizatórias: redireciona para editor específico.
    - Status de edição parcial (`STATUS_SOMENTE_DOCUMENTOS`): permite alterar
      apenas documentos (capa e pendências ficam protegidas).
    - Demais status: permite edição completa.

    Também calcula contexto auxiliar para a UI, como:
    - URL de documentos fiscais.
    - Quantidade/lista de boletos com código de barras.
    - Flag de etapa "aguardando liquidação".

    Args:
        request: Requisição HTTP GET/POST.
        pk: ID do processo alvo.

    Returns:
        HttpResponse ou HttpResponseRedirect conforme validações e fluxo.
    """
    processo = get_object_or_404(Processo, id=pk)
    status_inicial = processo.status.status_choice.upper() if processo.status else ""
    redirecionamento, somente_documentos = _validar_regras_edicao_processo(request, processo, status_inicial)
    if redirecionamento:
        return redirecionamento

    if request.method == "POST":
        documento_formset = DocumentoFormSet(request.POST, request.FILES, instance=processo, prefix="documento")
        next_url = request.POST.get("next", "")

        if somente_documentos:
            if documento_formset.is_valid():
                try:
                    with transaction.atomic():
                        documento_formset.save()

                    messages.success(request, f"Documentos do Processo #{pk} atualizados com sucesso!")
                    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                        return redirect(next_url)
                    return redirect("editar_processo", pk=pk)
                except Exception as e:
                    print(f"🛑 Erro ao atualizar documentos: {e}")
                    messages.error(request, "Erro interno ao salvar os documentos.")
            else:
                messages.error(request, "Verifique os erros nos documentos.")
            processo_form = ProcessoForm(instance=processo, prefix="processo")
            pendencia_formset = PendenciaFormSet(instance=processo, prefix="pendencia")
        else:
            confirmar_extra = request.POST.get("confirmar_extra_orcamentario") == "on"
            processo_form = ProcessoForm(request.POST, instance=processo, prefix="processo")
            pendencia_formset = PendenciaFormSet(request.POST, instance=processo, prefix="pendencia")

            if processo_form.is_valid() and documento_formset.is_valid() and pendencia_formset.is_valid():
                try:
                    def _aplicar_confirmacao_extra(processo):
                        _aplicar_confirmacao_extra_orcamentario(processo, confirmar_extra, status_inicial)

                    processo_saved = _salvar_processo_completo(
                        processo_form,
                        documento_formset,
                        pendencia_formset,
                        mutator_func=_aplicar_confirmacao_extra,
                    )

                    messages.success(request, f"Processo #{processo_saved.id} atualizado com sucesso!")
                    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                        return redirect(next_url)
                    return redirect("editar_processo", pk=processo_saved.id)
                except Exception as e:
                    print(f"🛑 Erro ao atualizar no banco: {e}")
                    messages.error(request, "Erro interno ao salvar as alterações.")
            else:
                messages.error(request, "Verifique os erros no formulário.")
    else:
        processo_form = ProcessoForm(instance=processo, prefix="processo")
        documento_formset = DocumentoFormSet(instance=processo, prefix="documento")
        pendencia_formset = PendenciaFormSet(instance=processo, prefix="pendencia")
        next_url = request.META.get("HTTP_REFERER", "")

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


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def a_empenhar_view(request):
    """Gerencia a fila de processos no status `A EMPENHAR`.

    POST:
    - Registra número/data de empenho.
    - Opcionalmente anexa documento orçamentário (SISCAC) e reordena anexos.
    - Persiste alterações em transação atômica e tenta avançar o processo para
      `AGUARDANDO LIQUIDAÇÃO` via regra de turnpike.

    GET:
    - Exibe listagem filtrável/ordenável de processos em `A EMPENHAR`.

    Args:
        request: Requisição HTTP GET/POST.

    Returns:
        HttpResponse ou HttpResponseRedirect para a própria fila.
    """
    if request.method == "POST":
        pode_interagir = request.user.has_perm("processos.pode_operar_contas_pagar")
        if not pode_interagir:
            raise PermissionDenied
        processo_id = request.POST.get("processo_id")
        n_nota_empenho = request.POST.get("n_nota_empenho")
        data_empenho_str = request.POST.get("data_empenho")
        siscac_file = request.FILES.get("siscac_file")

        if processo_id and n_nota_empenho and data_empenho_str:
            try:
                with transaction.atomic():
                    processo = Processo.objects.get(id=processo_id)
                    processo.n_nota_empenho = n_nota_empenho
                    processo.data_empenho = datetime.strptime(data_empenho_str, "%Y-%m-%d").date()

                    if siscac_file:
                        tipo_doc, _ = TiposDeDocumento.objects.get_or_create(
                            tipo_de_documento__iexact="DOCUMENTOS ORÇAMENTÁRIOS",
                            defaults={"tipo_de_documento": "DOCUMENTOS ORÇAMENTÁRIOS"},
                        )

                        for doc in processo.documentos.all().order_by("-ordem"):
                            doc.ordem += 1
                            doc.save()

                        DocumentoProcesso.objects.create(
                            processo=processo,
                            arquivo=siscac_file,
                            tipo=tipo_doc,
                            ordem=1,
                        )

                    processo.save(update_fields=["n_nota_empenho", "data_empenho"])
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
        else:
            messages.error(request, "Por favor, preencha o número e a data da nota de empenho para avançar.")

        return redirect("a_empenhar")

    processos_base = Processo.objects.filter(status__status_choice__iexact="A EMPENHAR").select_related(
        "credor", "status", "tipo_pagamento"
    )

    meu_filtro = AEmpenharFilter(request.GET, queryset=processos_base)

    ORDER_FIELDS = {
        "id": "id",
        "credor": "credor__nome",
        "valor_liquido": "valor_liquido",
        "data_vencimento": "data_vencimento",
        "tipo_pagamento": "tipo_pagamento__tipo_de_pagamento",
    }
    ordem = request.GET.get("ordem", "data_vencimento")
    direcao = request.GET.get("direcao", "asc")
    order_field = ORDER_FIELDS.get(ordem, "data_vencimento")
    if direcao == "desc":
        order_field = f"-{order_field}"

    processos_pendentes = meu_filtro.qs.order_by(order_field, "-id")

    context = {
        "processos": processos_pendentes,
        "meu_filtro": meu_filtro,
        "ordem": ordem,
        "direcao": direcao,
        "pode_interagir": request.user.has_perm("processos.pode_operar_contas_pagar"),
    }
    return render(request, "fluxo/a_empenhar.html", context)


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def avancar_para_pagamento_view(request, pk):
    """Avança um processo de liquidação para pagamento autorizado a operar.

    Pré-condições:
    - Método POST.
    - Processo em status iniciado por `AGUARDANDO LIQUIDAÇÃO`.

    Em sucesso, avança o status para `A PAGAR - PENDENTE AUTORIZAÇÃO` dentro
    de transação atômica e registra mensagens de retorno ao usuário.

    Args:
        request: Requisição HTTP atual.
        pk: ID do processo a avançar.

    Returns:
        HttpResponseRedirect: Sempre retorna para a tela de edição do processo.
    """
    processo = get_object_or_404(Processo, id=pk)

    if request.method != "POST":
        return redirect("editar_processo", pk=pk)

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
    "avancar_para_pagamento_view",
]
