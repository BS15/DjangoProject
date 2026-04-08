"""Painel de auditoria consolidada."""

from urllib.parse import urlencode

from django.contrib.auth.decorators import permission_required
from django.db import OperationalError, ProgrammingError
from django.shortcuts import render

from ....models import (
    AssinaturaAutentique,
    CargosFuncoes,
    ComprovanteDePagamento,
    ContaFixa,
    ContasBancarias,
    DadosContribuinte,
    Devolucao,
    DocumentoAuxilio,
    DocumentoDePagamento,
    DocumentoDiaria,
    DocumentoFiscal,
    DocumentoJeton,
    DocumentoReembolso,
    DocumentoSuprimentoDeFundos,
    FaturaMensal,
    Processo,
    RegistroAcessoArquivo,
    RetencaoImposto,
    SuprimentoDeFundos,
)
from ....utils import normalize_choice
from ..helpers import _aplicar_filtros_historico


@permission_required("processos.pode_auditar_conselho", raise_exception=True)
def auditoria_view(request):
    """Renderiza a trilha de auditoria consolidada de modelos financeiros."""
    history_type_labels = {"+": "Criação", "~": "Alteração", "-": "Exclusão"}

    model_configs = [
        (Processo.history.model, "Processo"),
        (ContasBancarias.history.model, "Conta Bancária"),
        (CargosFuncoes.history.model, "Cargo/Função"),
        (DadosContribuinte.history.model, "Dados do Contribuinte"),
        (ContaFixa.history.model, "Conta Fixa"),
        (FaturaMensal.history.model, "Fatura Mensal"),
        (DocumentoDePagamento.history.model, "Documento de Pagamento"),
        (DocumentoFiscal.history.model, "Documento Fiscal"),
        (RetencaoImposto.history.model, "Retenção de Imposto"),
        (ComprovanteDePagamento.history.model, "Comprovante de Pagamento"),
        (Devolucao.history.model, "Devolução"),
        (SuprimentoDeFundos.history.model, "Suprimento de Fundos"),
        (DocumentoDiaria.history.model, "Documento de Diária"),
        (DocumentoReembolso.history.model, "Documento de Reembolso"),
        (DocumentoJeton.history.model, "Documento de Jeton"),
        (DocumentoAuxilio.history.model, "Documento de Auxílio"),
        (DocumentoSuprimentoDeFundos.history.model, "Documento de Suprimento"),
        (RegistroAcessoArquivo.history.model, "Registro de Acesso a Arquivo"),
        (AssinaturaAutentique.history.model, "Assinatura Autentique"),
    ]

    modelos_disponiveis = [label for _, label in model_configs]
    modelo_filter = normalize_choice(
        request.GET.get("modelo", "").strip(),
        {*modelos_disponiveis, ""},
        default="",
    )
    tipo_filter = normalize_choice(
        request.GET.get("tipo_acao", "").strip(),
        {"", "+", "~", "-"},
        default="",
    )
    data_inicio = request.GET.get("data_inicio", "").strip()
    data_fim = request.GET.get("data_fim", "").strip()
    usuario_filter = request.GET.get("usuario", "").strip()
    ordem = normalize_choice(
        request.GET.get("ordem", "data"),
        {"data", "modelo", "id", "acao", "usuario", "descricao"},
        default="data",
    )
    direcao = normalize_choice(
        request.GET.get("direcao", "desc"),
        {"asc", "desc"},
        default="desc",
    )

    campos_ordenacao = {
        "data": "history_date",
        "modelo": "modelo",
        "id": "object_id",
        "acao": "history_type",
        "usuario": "history_user",
        "descricao": "str_repr",
    }
    sort_key = campos_ordenacao[ordem]
    reverse_sort = direcao == "desc"

    all_records = []
    for history_model, label in model_configs:
        if modelo_filter and modelo_filter != label:
            continue
        try:
            qs = history_model.objects.select_related("history_user").all()
            qs.exists()  # força validação de tabela no banco antes do loop
        except (OperationalError, ProgrammingError):
            # Alguns ambientes de teste legados não têm todas as tabelas historical*.
            # Ignoramos o modelo ausente para manter a auditoria utilizável.
            continue
        qs = _aplicar_filtros_historico(
            qs,
            tipo_acao=tipo_filter,
            data_inicio=data_inicio,
            data_fim=data_fim,
            usuario=usuario_filter,
        )
        for record in qs:
            all_records.append(
                {
                    "modelo": label,
                    "object_id": record.id,
                    "history_date": record.history_date,
                    "history_user": record.history_user,
                    "history_type": record.history_type,
                    "history_type_label": history_type_labels.get(record.history_type, record.history_type),
                    "history_change_reason": getattr(record, "history_change_reason", None),
                    "str_repr": str(record),
                }
            )

    def _record_sort_key(record):
        if sort_key == "history_user":
            user = record.get("history_user")
            if not user:
                return ""
            return (user.get_full_name() or user.username or "").lower()

        value = record.get(sort_key)
        if value is None:
            return ""
        if isinstance(value, str):
            return value.lower()
        return value

    all_records.sort(key=_record_sort_key, reverse=reverse_sort)
    total = len(all_records)
    all_records = all_records[:500]

    sort_base_qs = urlencode(
        {
            "modelo": modelo_filter,
            "tipo_acao": tipo_filter,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "usuario": usuario_filter,
        }
    )
    sort_base_qs = f"{sort_base_qs}&" if sort_base_qs else ""

    context = {
        "registros": all_records,
        "total": total,
        "modelos_disponiveis": modelos_disponiveis,
        "ordem": ordem,
        "direcao": direcao,
        "sort_base_qs": sort_base_qs,
        "filtros": {
            "modelo": modelo_filter,
            "tipo_acao": tipo_filter,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "usuario": usuario_filter,
        },
    }
    return render(request, "fluxo/auditoria.html", context)


__all__ = ["auditoria_view"]