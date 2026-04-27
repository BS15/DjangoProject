"""Servicos canonicos para registro de devolucao de diarias."""

from django.db import transaction


def registrar_devolucao_diaria(diaria, form, usuario):
    """Persiste devolucao validada, vinculando diaria e usuario que registrou."""
    with transaction.atomic():
        devolucao = form.save(commit=False)
        devolucao.diaria = diaria
        devolucao.registrado_por = usuario
        devolucao.full_clean()
        devolucao.save()
    return devolucao


__all__ = ["registrar_devolucao_diaria"]
