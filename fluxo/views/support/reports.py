from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse
from django.shortcuts import render

from fiscal.filters import RetencaoIndividualFilter
from fiscal.models import RetencaoImposto
from fluxo.filters import ProcessoFilter
from fluxo.models import Processo
from fluxo.views.helpers.reports import gerar_csv_relatorio
from fluxo.views.shared import apply_filterset
from verbas_indenizatorias.filters import DiariaFilter
from verbas_indenizatorias.models import Diaria


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def painel_relatorios_view(request):
    tipo = request.GET.get("tipo", "processos")
    exportar = request.GET.get("exportar")

    if tipo == "processos":
        filtro = apply_filterset(request, ProcessoFilter, Processo.objects.all().order_by("-id"))
    elif tipo == "diarias":
        filtro = apply_filterset(request, DiariaFilter, Diaria.objects.all().order_by("-id"))
    elif tipo == "impostos":
        filtro = apply_filterset(request, RetencaoIndividualFilter, RetencaoImposto.objects.all().order_by("-id"))
    else:
        filtro = None

    if exportar == "csv" and filtro:
        return gerar_csv_relatorio(filtro.qs, tipo)

    context = {"tipo": tipo, "filtro": filtro}
    return render(request, "relatorios/painel.html", context)


@permission_required("fluxo.acesso_backoffice", raise_exception=True)
def relatorio_documentos_gerados_view(request):
    """Audita lacunas de documentos PDF gerados automaticamente no fluxo."""
    processos = (
        Processo.objects.select_related("status")
        .prefetch_related(
            "documentos__tipo",
            "diarias",
            "reembolsos_combustivel",
            "jetons",
            "auxilios_representacao",
            "suprimentos",
        )
        .order_by("id")
    )

    totais = {
        "processos_analisados": 0,
        "processos_com_pendencias": 0,
        "faltando_termo_autorizacao": 0,
        "faltando_termo_contabilizacao": 0,
        "faltando_termo_auditoria": 0,
        "faltando_parecer_conselho": 0,
        "faltando_pcd": 0,
        "faltando_recibos": 0,
        "diarias_analisadas": 0,
        "diarias_sem_scd": 0,
    }
    pendencias = []

    for processo in processos:
        totais["processos_analisados"] += 1

        status = (processo.status.status_choice if processo.status else "").upper()
        tipos_documentos = {
            (doc.tipo.tipo_de_documento or "").upper()
            for doc in processo.documentos.all()
            if doc.tipo
        }

        diaria_count = processo.diarias.count()
        recibos_esperados = (
            processo.reembolsos_combustivel.count()
            + processo.jetons.count()
            + processo.auxilios_representacao.count()
            + processo.suprimentos.count()
        )
        recibos_gerados = sum(
            1
            for doc in processo.documentos.all()
            if doc.tipo and (doc.tipo.tipo_de_documento or "").upper() == "RECIBO DE PAGAMENTO"
        )

        processo_pendencias = []

        if status in {
            "A PAGAR - AUTORIZADO",
            "LANÇADO - AGUARDANDO COMPROVANTE",
            "PAGO - EM CONFERÊNCIA",
            "PAGO - A CONTABILIZAR",
            "CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL",
            "APROVADO - PENDENTE ARQUIVAMENTO",
            "ARQUIVADO",
        } and "TERMO DE AUTORIZAÇÃO DE PAGAMENTO" not in tipos_documentos:
            processo_pendencias.append("TERMO DE AUTORIZAÇÃO")
            totais["faltando_termo_autorizacao"] += 1

        if status in {
            "CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL",
            "APROVADO - PENDENTE ARQUIVAMENTO",
            "ARQUIVADO",
        }:
            if "TERMO DE CONTABILIZAÇÃO" not in tipos_documentos:
                processo_pendencias.append("TERMO DE CONTABILIZAÇÃO")
                totais["faltando_termo_contabilizacao"] += 1
            if "TERMO DE AUDITORIA" not in tipos_documentos:
                processo_pendencias.append("TERMO DE AUDITORIA")
                totais["faltando_termo_auditoria"] += 1

        if status in {"APROVADO - PENDENTE ARQUIVAMENTO", "ARQUIVADO"} and "PARECER DO CONSELHO FISCAL" not in tipos_documentos:
            processo_pendencias.append("PARECER DO CONSELHO FISCAL")
            totais["faltando_parecer_conselho"] += 1

        if status.startswith("PAGO") or status in {
            "CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL",
            "APROVADO - PENDENTE ARQUIVAMENTO",
            "ARQUIVADO",
        }:
            pcd_gerado = sum(
                1
                for doc in processo.documentos.all()
                if doc.tipo and (doc.tipo.tipo_de_documento or "").upper() == "PROPOSTA DE CONCESSÃO DE DIÁRIAS (PCD)"
            )
            if diaria_count and pcd_gerado < diaria_count:
                processo_pendencias.append("PCD")
                totais["faltando_pcd"] += 1

            if recibos_esperados and recibos_gerados < recibos_esperados:
                processo_pendencias.append("RECIBOS")
                totais["faltando_recibos"] += 1

        if processo_pendencias:
            totais["processos_com_pendencias"] += 1
            pendencias.append(
                {
                    "processo_id": processo.id,
                    "status": status,
                    "pendencias": sorted(set(processo_pendencias)),
                    "diarias": diaria_count,
                    "recibos_esperados": recibos_esperados,
                    "recibos_gerados": recibos_gerados,
                }
            )

    diarias = Diaria.objects.prefetch_related("documentos__tipo").all().order_by("id")
    diarias_sem_scd = []
    for diaria in diarias:
        totais["diarias_analisadas"] += 1
        tem_scd = any(
            doc.tipo and (doc.tipo.tipo_de_documento or "").upper() == "SOLICITAÇÃO DE CONCESSÃO DE DIÁRIAS (SCD)"
            for doc in diaria.documentos.all()
        )
        if not tem_scd:
            totais["diarias_sem_scd"] += 1
            diarias_sem_scd.append(
                {
                    "diaria_id": diaria.id,
                    "numero_siscac": diaria.numero_siscac,
                    "beneficiario": diaria.beneficiario.nome if diaria.beneficiario else None,
                }
            )

    payload = {
        "totais": totais,
        "processos_com_lacunas": pendencias,
        "diarias_sem_scd": diarias_sem_scd,
    }
    return JsonResponse(payload)
