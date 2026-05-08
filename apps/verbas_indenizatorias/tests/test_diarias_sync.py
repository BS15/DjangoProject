"""Testes para verbas_indenizatorias/services/diarias_sync.py."""

import io

import pytest

from apps.verbas_indenizatorias.services.diarias_sync import sincronizar_numero_siscac_csv


def _csv(content: str) -> io.BytesIO:
    return io.BytesIO(content.encode("utf-8"))


# --- Cenários de sucesso ---

@pytest.mark.django_db
def test_atualiza_numero_siscac_por_id(diaria_factory):
    diaria = diaria_factory(numero_siscac=None)
    csv_data = _csv(f"DIARIA_ID,NUMERO_SISCAC\n{diaria.pk},SISCAC-001\n")
    resultado = sincronizar_numero_siscac_csv(csv_data)
    assert resultado["atualizadas"] == 1
    assert resultado["erros"] == []
    diaria.refresh_from_db()
    assert diaria.numero_siscac == "SISCAC-001"


@pytest.mark.django_db
def test_atualiza_usando_coluna_id_diaria(diaria_factory):
    diaria = diaria_factory(numero_siscac=None)
    csv_data = _csv(f"ID_DIARIA,N_SISCAC\n{diaria.pk},ABC-99\n")
    resultado = sincronizar_numero_siscac_csv(csv_data)
    assert resultado["atualizadas"] == 1
    diaria.refresh_from_db()
    assert diaria.numero_siscac == "ABC-99"


@pytest.mark.django_db
def test_nao_atualiza_quando_siscac_ja_igual(diaria_factory):
    diaria = diaria_factory(numero_siscac="SISCAC-EXISTENTE")
    csv_data = _csv(f"DIARIA_ID,NUMERO_SISCAC\n{diaria.pk},SISCAC-EXISTENTE\n")
    resultado = sincronizar_numero_siscac_csv(csv_data)
    assert resultado["atualizadas"] == 0
    assert resultado["erros"] == []


@pytest.mark.django_db
def test_processa_multiplas_linhas(diaria_factory):
    d1 = diaria_factory(numero_siscac=None)
    d2 = diaria_factory(numero_siscac=None)
    csv_data = _csv(
        f"DIARIA_ID,NUMERO_SISCAC\n"
        f"{d1.pk},SC-001\n"
        f"{d2.pk},SC-002\n"
    )
    resultado = sincronizar_numero_siscac_csv(csv_data)
    assert resultado["atualizadas"] == 2
    assert resultado["erros"] == []
    d1.refresh_from_db()
    d2.refresh_from_db()
    assert d1.numero_siscac == "SC-001"
    assert d2.numero_siscac == "SC-002"


# --- Cenários de erro ---

@pytest.mark.django_db
def test_csv_vazio_nao_gera_atualizacoes_nem_erros():
    """CSV sem linhas de dados não deve gerar atualizações nem erros."""
    csv_data = _csv("DIARIA_ID,NUMERO_SISCAC\n")
    resultado = sincronizar_numero_siscac_csv(csv_data)
    assert resultado["atualizadas"] == 0
    assert resultado["erros"] == []


@pytest.mark.django_db
def test_erro_id_diaria_ausente():
    csv_data = _csv("DIARIA_ID,NUMERO_SISCAC\n,SISCAC-001\n")
    resultado = sincronizar_numero_siscac_csv(csv_data)
    assert resultado["atualizadas"] == 0
    assert any("identificador" in e for e in resultado["erros"])


@pytest.mark.django_db
def test_erro_numero_siscac_ausente(diaria_factory):
    diaria = diaria_factory()
    csv_data = _csv(f"DIARIA_ID,NUMERO_SISCAC\n{diaria.pk},\n")
    resultado = sincronizar_numero_siscac_csv(csv_data)
    assert resultado["atualizadas"] == 0
    assert any("SISCAC" in e for e in resultado["erros"])


@pytest.mark.django_db
def test_erro_id_invalido_nao_inteiro():
    csv_data = _csv("DIARIA_ID,NUMERO_SISCAC\nabc,SISCAC-001\n")
    resultado = sincronizar_numero_siscac_csv(csv_data)
    assert resultado["atualizadas"] == 0
    assert any("invalido" in e for e in resultado["erros"])


@pytest.mark.django_db
def test_erro_diaria_nao_encontrada():
    csv_data = _csv("DIARIA_ID,NUMERO_SISCAC\n99999999,SISCAC-001\n")
    resultado = sincronizar_numero_siscac_csv(csv_data)
    assert resultado["atualizadas"] == 0
    assert any("nao encontrada" in e for e in resultado["erros"])


@pytest.mark.django_db
def test_erros_parciais_nao_interrompem_restante(diaria_factory):
    """Linha com ID inválido não impede a atualização de linhas válidas seguintes."""
    diaria = diaria_factory(numero_siscac=None)
    csv_data = _csv(
        f"DIARIA_ID,NUMERO_SISCAC\n"
        f"invalido,SC-X\n"
        f"{diaria.pk},SC-VALIDO\n"
    )
    resultado = sincronizar_numero_siscac_csv(csv_data)
    assert resultado["atualizadas"] == 1
    assert len(resultado["erros"]) == 1
    diaria.refresh_from_db()
    assert diaria.numero_siscac == "SC-VALIDO"
