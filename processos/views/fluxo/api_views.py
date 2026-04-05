"""Views de API do fluxo de pagamentos (exceto auditoria/histórico).

Este módulo concentra endpoints auxiliares usados pela interface do fluxo para:
- extração de códigos de barras e metadados de boletos;
- extração de dados de empenho a partir de PDF SISCAC;
- carregamento dinâmico de tipos documentais por tipo de pagamento;
- montagem de payload resumido para painéis de pagamento;
- visualização/geração de PDFs operacionais.

As regras de segurança seguem o padrão do projeto com `permission_required` e
respostas em `JsonResponse` para chamadas assíncronas.
"""

import json
import logging

from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.clickjacking import xframe_options_sameorigin

from ...models import Processo, TiposDeDocumento
from ...utils import extract_siscac_data, format_brl_amount, processar_pdf_boleto
from ...services import gerar_resposta_pdf, montar_resposta_pdf


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def api_extrair_codigos_barras_processo(request, pk):
    """Retorna códigos de barras já persistidos nos documentos de um processo.

    Consulta os documentos vinculados ao processo, filtra apenas tipos cujo nome
    contenha "boleto" e devolve os valores de `codigo_barras` já armazenados.
    Não executa OCR nem reprocessamento de PDF; apenas leitura de dados já
    extraídos anteriormente.

    Parâmetros:
        request: Requisição HTTP autenticada.
        pk: ID do processo alvo.

    Retorna:
        JsonResponse: Payload com `sucesso`, `processo_id`, quantidade de
        documentos de boleto, quantidade efetivamente extraída e lista de
        códigos encontrados.
    """
    processo = get_object_or_404(Processo, id=pk)
    boleto_docs_qs = processo.documentos.select_related("tipo").filter(
        tipo__tipo_de_documento__icontains="boleto"
    )
    barcodes = [doc.codigo_barras for doc in boleto_docs_qs if doc.codigo_barras]
    return JsonResponse(
        {
            "sucesso": True,
            "processo_id": processo.id,
            "n_documentos_boleto": boleto_docs_qs.count(),
            "n_extraidos": len(barcodes),
            "barcodes": barcodes,
        }
    )


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def api_extrair_codigos_barras_upload(request):
    """Extrai dados de boleto a partir de upload único ou em lote de PDFs.

    Contrato do endpoint:
    - Aceita `POST` com arquivos em `boleto_files` (lote) ou
      `boleto_file`/`boleto_pdf`/`file` (único).
    - Em upload único, retorna o dicionário completo produzido por
      `processar_pdf_boleto` em `dados`.
    - Em lote, retorna lista de códigos válidos e contadores de sucesso/falha.

    Regras de resposta:
    - `405` para método inválido.
    - `400` quando nenhum arquivo é enviado.
    - `500` em erro interno de processamento do PDF.

    Parâmetros:
        request: Requisição HTTP contendo arquivos multipart.

    Retorna:
        JsonResponse: Estrutura de sucesso/erro adequada ao modo de envio.
    """
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "erro": "Método não permitido."}, status=405)

    files = request.FILES.getlist("boleto_files")
    if not files:
        single_file = (
            request.FILES.get("boleto_file")
            or request.FILES.get("boleto_pdf")
            or request.FILES.get("file")
        )
        if single_file:
            files = [single_file]
    
    if not files:
        return JsonResponse({"sucesso": False, "erro": "Nenhum arquivo enviado."}, status=400)

    if len(files) == 1:
        try:
            dados = processar_pdf_boleto(files[0]) or {}
        except Exception as e:
            logging.getLogger(__name__).exception(
                "Erro ao processar boleto no upload %s", getattr(files[0], "name", "")
            )
            return JsonResponse(
                {
                    "sucesso": False,
                    "erro": "Erro ao processar boleto. Verifique se o arquivo é um PDF válido.",
                },
                status=500,
            )
        return JsonResponse({"sucesso": True, "dados": dados})
    
    barcodes = []
    n_extraidos = 0
    n_falhas = 0

    for pdf_file in files:
        try:
            dados = processar_pdf_boleto(pdf_file)
            codigo = dados.get("codigo_barras", "") if dados else ""
            if codigo:
                barcodes.append(codigo)
                n_extraidos += 1
            else:
                barcodes.append(None)
                n_falhas += 1
        except Exception as e:
            logging.getLogger(__name__).exception(
                "Erro ao extrair código de barras de '%s'", getattr(pdf_file, "name", "arquivo")
            )
            barcodes.append(None)
            n_falhas += 1

    return JsonResponse(
        {
            "sucesso": True,
            "n_extraidos": n_extraidos,
            "n_falhas": n_falhas,
            "barcodes": [b for b in barcodes if b],
        }
    )


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def api_extrair_dados_empenho(request):
    """Extrai número e data de empenho a partir de PDF SISCAC enviado pelo usuário.

    Endpoint utilizado para preenchimento automático dos campos de empenho na
    camada de pré-pagamento. Invoca `extract_siscac_data` e valida se ao menos
    um dos campos esperados (`n_nota_empenho` ou `data_empenho`) foi obtido.

    Regras de resposta:
    - `405` para método diferente de `POST`.
    - `400` sem arquivo em `siscac_file`.
    - `500` para falha técnica no parser.
    - `422` quando o arquivo é processado, mas não contém dados de empenho.

    Parâmetros:
        request: Requisição HTTP contendo `siscac_file`.

    Retorna:
        JsonResponse: Em sucesso, retorna `n_nota_empenho` e `data_empenho` em
        formato ISO (`YYYY-MM-DD`).
    """
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "erro": "Método não permitido."}, status=405)

    siscac_file = request.FILES.get("siscac_file")
    if not siscac_file:
        return JsonResponse({"sucesso": False, "erro": "Nenhum arquivo enviado."}, status=400)

    try:
        data = extract_siscac_data(siscac_file)
    except Exception:
        logging.getLogger(__name__).exception(
            "Erro ao extrair dados de empenho do arquivo %s", getattr(siscac_file, "name", "")
        )
        return JsonResponse(
            {
                "sucesso": False,
                "erro": "Erro ao processar o arquivo. Verifique se é um PDF SISCAC válido.",
            },
            status=500,
        )

    n_nota_empenho = data.get("n_nota_empenho") or ""
    data_empenho = data.get("data_empenho")
    data_empenho_iso = data_empenho if data_empenho else ""

    if not n_nota_empenho and not data_empenho_iso:
        return JsonResponse(
            {
                "sucesso": False,
                "erro": "Não foi possível extrair dados de empenho do arquivo. Verifique se é um documento SISCAC válido.",
            },
            status=422,
        )

    return JsonResponse(
        {
            "sucesso": True,
            "n_nota_empenho": n_nota_empenho,
            "data_empenho": data_empenho_iso,
        }
    )


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def api_tipos_documento_por_pagamento(request):
    """Lista tipos de documento ativos vinculados a um tipo de pagamento.

    Endpoint de apoio para formulários dinâmicos (dropdown dependente),
    retornando apenas os campos necessários (`id` e `tipo_de_documento`) em
    ordem alfabética.

    Parâmetros:
        request: Requisição HTTP com query param `tipo_pagamento_id`.

    Retorna:
        JsonResponse: `sucesso=True` com lista em `tipos` ou `sucesso=False`
        com mensagem de erro quando o parâmetro é ausente ou ocorre exceção.
    """
    tipo_pagamento_id = request.GET.get("tipo_pagamento_id")

    if not tipo_pagamento_id:
        return JsonResponse({"sucesso": False, "erro": "ID não fornecido"})

    try:
        documentos_validos = (
            TiposDeDocumento.objects.filter(tipo_de_pagamento_id=tipo_pagamento_id, is_active=True)
            .values("id", "tipo_de_documento")
            .order_by("tipo_de_documento")
        )

        lista_docs = list(documentos_validos)
        return JsonResponse({"sucesso": True, "tipos": lista_docs})
    except Exception as e:
        return JsonResponse({"sucesso": False, "erro": str(e)})


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def api_detalhes_pagamento(request):
    """Monta resumo de detalhes de pagamento para uma lista de processos.

    Espera `POST` JSON com `ids` e retorna payload normalizado para exibição em
    painéis de pagamento/autorização, incluindo:
    - dados básicos do processo e credor;
    - valor líquido formatado em padrão brasileiro;
    - forma de pagamento;
    - detalhes derivados de `processo.detalhes_pagamento`.

    Em caso de exceção, captura o erro e devolve mensagem no payload para
    tratamento no frontend.

    Parâmetros:
        request: Requisição HTTP com corpo JSON.

    Retorna:
        JsonResponse: `sucesso=True` com lista em `dados` quando o `POST` é
        válido; caso contrário, `sucesso=False` com descrição do erro.
    """
    if request.method == "POST":
        try:
            dados = json.loads(request.body)
            processo_ids = dados.get("ids", [])

            processos = (
                Processo.objects.filter(id__in=processo_ids)
                .select_related("forma_pagamento", "conta", "credor")
                .prefetch_related("documentos")
            )

            resultados = []
            for p in processos:
                valor_formatado = format_brl_amount(p.valor_liquido, empty_value="0,00")

                pagamento = p.detalhes_pagamento

                resultados.append(
                    {
                        "id": p.id,
                        "empenho": p.n_nota_empenho or "S/N",
                        "credor": p.credor.nome if p.credor else "Sem Credor",
                        "valor": valor_formatado,
                        "forma": p.forma_pagamento.forma_de_pagamento if p.forma_pagamento else "N/A",
                        "detalhe_tipo": pagamento["tipo_formatado"],
                        "detalhe_valor": pagamento["valor_formatado"],
                        "codigos_barras": pagamento["codigos_barras"],
                    }
                )

            return JsonResponse({"sucesso": True, "dados": resultados})
        except Exception as e:
            import traceback

            traceback.print_exc()
            return JsonResponse({"sucesso": False, "erro": str(e)})

    return JsonResponse({"sucesso": False, "erro": "Método inválido"})


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
@xframe_options_sameorigin
def visualizar_pdf_processo(request, processo_id):
    """Renderiza o PDF consolidado de documentos anexados ao processo.

    Gera visualização inline no navegador usando o consolidado retornado por
    `Processo.gerar_pdf_consolidado()`. Se o processo não tiver documentos PDF
    compatíveis, responde com `404` e mensagem textual.

    Parâmetros:
        request: Requisição HTTP autenticada.
        processo_id: ID do processo para geração do consolidado.

    Retorna:
        HttpResponse: Conteúdo `application/pdf` inline quando disponível.
    """
    processo = get_object_or_404(Processo, id=processo_id)

    pdf_buffer = processo.gerar_pdf_consolidado()

    if pdf_buffer is None:
        return HttpResponse("Este processo ainda não possui documentos em PDF anexados.", status=404)

    nome_arquivo = f"Processo_{processo.n_nota_empenho or processo.id}.pdf"
    return montar_resposta_pdf(pdf_buffer, nome_arquivo, inline=True)


@permission_required("processos.pode_autorizar_pagamento", raise_exception=True)
@xframe_options_sameorigin
def gerar_autorizacao_pagamento_view(request, pk):
    """Gera e exibe o PDF de autorização de pagamento de um processo.

    Utiliza o motor de documentos (`gerar_documento_pdf`) com template lógico
    `autorizacao` e retorna o resultado para visualização inline.

    Parâmetros:
        request: Requisição HTTP autenticada com permissão de autorização.
        pk: ID do processo para o qual a autorização será gerada.

    Retorna:
        HttpResponse: PDF inline com nome de arquivo padronizado.
    """
    processo = get_object_or_404(Processo, pk=pk)
    nome_arquivo = f"Autorizacao_Pagamento_Proc_{processo.id}.pdf"
    return gerar_resposta_pdf("autorizacao", processo, nome_arquivo, inline=True)


__all__ = [
    "api_extrair_codigos_barras_processo",
    "api_extrair_codigos_barras_upload",
    "api_extrair_dados_empenho",
    "api_tipos_documento_por_pagamento",
    "api_detalhes_pagamento",
    "visualizar_pdf_processo",
    "gerar_autorizacao_pagamento_view",
]
