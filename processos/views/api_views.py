"""Views de API do fluxo (exceto auditoria/historico, em modulo proprio)."""

import json
import logging

from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.clickjacking import xframe_options_sameorigin

from ..models import Processo, TiposDeDocumento
from ..utils import extract_siscac_data, processar_pdf_boleto
from ..pdf_engine import gerar_documento_pdf


@permission_required("processos.pode_operar_contas_pagar", raise_exception=True)
def api_extrair_codigos_barras_processo(request, pk):
    """Retorna codigos de barras ja extraidos dos documentos de boleto do processo."""
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
    """Extrai códigos de barras e dados de boletos de múltiplos (ou único) PDF(s).
    
    Aceita tanto uploads em lote via 'boleto_files' quanto upload único via
    'boleto_file'/'boleto_pdf'. Retorna dados completos para single upload
    ou array de códigos para batch.
    """
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "erro": "Método não permitido."}, status=405)

    # Suporta tanto batch (boleto_files) quanto single upload (boleto_file, boleto_pdf)
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

    # Single file: return full extraction data; batch: return barcodes array
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
    
    # Batch: extract barcodes from multiple files
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


def api_tipos_documento_por_pagamento(request):
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


def api_detalhes_pagamento(request):
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
                try:
                    valor_num = float(p.valor_liquido) if p.valor_liquido else 0.0
                    valor_formatado = f"{valor_num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                except (ValueError, TypeError):
                    valor_formatado = "0,00"

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


@xframe_options_sameorigin
def visualizar_pdf_processo(request, processo_id):
    processo = get_object_or_404(Processo, id=processo_id)

    pdf_buffer = processo.gerar_pdf_consolidado()

    if pdf_buffer is None:
        return HttpResponse("Este processo ainda não possui documentos em PDF anexados.", status=404)

    response = HttpResponse(pdf_buffer, content_type="application/pdf")
    nome_arquivo = f"Processo_{processo.n_nota_empenho or processo.id}.pdf"
    response["Content-Disposition"] = f'inline; filename="{nome_arquivo}"'
    return response


@permission_required("processos.pode_autorizar_pagamento", raise_exception=True)
@xframe_options_sameorigin
def gerar_autorizacao_pagamento_view(request, pk):
    processo = get_object_or_404(Processo, pk=pk)
    pdf_bytes = gerar_documento_pdf("autorizacao", processo)
    nome_arquivo = f"Autorizacao_Pagamento_Proc_{processo.id}.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{nome_arquivo}"'
    return response


__all__ = [
    "api_extrair_codigos_barras_processo",
    "api_extrair_codigos_barras_upload",
    "api_extrair_dados_empenho",
    "api_tipos_documento_por_pagamento",
    "api_detalhes_pagamento",
    "visualizar_pdf_processo",
    "gerar_autorizacao_pagamento_view",
]
