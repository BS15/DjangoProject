"""Ações de negócio da etapa de cadastro de suprimentos."""

from typing import Any

from django.db import transaction

from suprimentos.services.processo_integration import criar_processo_para_suprimento
from suprimentos.forms import SuprimentoForm
from suprimentos.models import StatusChoicesSuprimentoDeFundos


def persistir_suprimento_com_processo(form_suprimento: SuprimentoForm) -> Any:
    """Persiste suprimento e cria o processo financeiro vinculado em transação atômica."""
    with transaction.atomic():
        suprimento: Any = form_suprimento.save(commit=False)
        status_aberto, _ = StatusChoicesSuprimentoDeFundos.objects.get_or_create(status_choice="ABERTO")
        suprimento.status = status_aberto
        suprimento.save()

        nome_lotacao = suprimento.lotacao or "Unidade Não Especificada"
        detalhamento = (
            f"Referente a suprimento de fundos da {nome_lotacao} "
            f"- mês {suprimento.data_saida.month}/{suprimento.data_saida.year}"
        )

        criar_processo_para_suprimento(suprimento, detalhamento)
        return suprimento


__all__ = ["persistir_suprimento_com_processo"]