import io
import uuid
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.urls import reverse
from pypdf import PdfWriter

from credores.models import Credor
from pagamentos.domain_models import (
    Boleto_Bancario,
    DocumentoProcesso,
    FormasPagamento,
    Processo,
    StatusChoicesProcesso,
    TiposDocumento,
    TiposPagamento,
)
from pagamentos.views.pre_payment.cadastro import actions as cadastro_actions


def _pdf_bytes():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _create_backoffice_user():
    user = get_user_model().objects.create_user(
        username=f"backoffice_{uuid.uuid4().hex[:8]}",
        email=f"backoffice_{uuid.uuid4().hex[:8]}@example.com",
        password="x",
    )
    permissao = Permission.objects.get(codename="operador_contas_a_pagar", content_type__app_label="pagamentos")
    user.user_permissions.add(permissao)
    return user


def _create_processo():
    credor = Credor.objects.create(
        nome=f"Credor {uuid.uuid4().hex[:6]}",
        cpf_cnpj=f"{uuid.uuid4().int % 10**11:011d}",
        tipo="PF",
    )
    forma_pagamento = FormasPagamento.objects.create(forma_pagamento=f"PIX-{uuid.uuid4().hex[:6]}")
    tipo_pagamento = TiposPagamento.objects.create(tipo_pagamento=f"SERVICO-{uuid.uuid4().hex[:6]}")
    status, _ = StatusChoicesProcesso.objects.get_or_create(
        opcao_status__iexact="AGUARDANDO LIQUIDAÇÃO",
        defaults={"opcao_status": "AGUARDANDO LIQUIDAÇÃO"},
    )
    return Processo.objects.create(
        credor=credor,
        valor_bruto=Decimal("100.00"),
        valor_liquido=Decimal("100.00"),
        forma_pagamento=forma_pagamento,
        tipo_pagamento=tipo_pagamento,
        status=status,
    )


def _create_tipo_documento(nome, tipo_pagamento):
    return TiposDocumento.objects.create(tipo_documento=nome, tipo_pagamento=tipo_pagamento)


def _add_documento(processo, tipo, ordem, nome_arquivo):
    return DocumentoProcesso.objects.create(
        processo=processo,
        tipo=tipo,
        ordem=ordem,
        arquivo=ContentFile(_pdf_bytes(), name=nome_arquivo),
    )


@pytest.mark.django_db
def test_editar_processo_documentos_action_ignora_linha_vazia_sem_arquivo(client):
    """Alteração de tipo de doc existente não falha se JS deixou linha fantasma sem arquivo.

    Quando o usuário clica em "Adicionar Documento" sem enviar um arquivo,
    o JS preenche automaticamente os campos 'tipo' e 'ordem' via ensureTipoSelection/
    syncOrderFields.  Isso faz o Django crer que há uma linha nova não-vazia e exige
    'arquivo'.  O override de has_changed() deve descartar silenciosamente essa linha
    para que a alteração de tipo dos documentos existentes seja salva normalmente.
    """
    processo = _create_processo()
    tipo_a = _create_tipo_documento("TIPO A", processo.tipo_pagamento)
    tipo_b = _create_tipo_documento("TIPO B", processo.tipo_pagamento)
    doc = _add_documento(processo, tipo_a, 1, "doc.pdf")

    user = _create_backoffice_user()
    client.force_login(user)

    # Simula o POST com TOTAL_FORMS=3 (N+1 do extra=1 + 1 adicionado pelo JS),
    # uma linha fantasma (index 1) com tipo e ordem preenchidos pelo JS, mas sem arquivo.
    response = client.post(
        reverse("editar_processo_documentos_action", kwargs={"pk": processo.id}),
        data={
            "documento-TOTAL_FORMS": "3",
            "documento-INITIAL_FORMS": "1",
            "documento-MIN_NUM_FORMS": "0",
            "documento-MAX_NUM_FORMS": "1000",
            "documento-0-id": str(doc.id),
            "documento-0-tipo": str(tipo_b.id),
            "documento-0-ordem": "1",
            # linha 1 = linha fantasma adicionada pelo JS sem arquivo
            "documento-1-tipo": str(tipo_a.id),
            "documento-1-ordem": "2",
            # linha 2 = extra server-side sem dados
            "next": "",
        },
        secure=True,
    )

    assert response.status_code == 302
    doc.refresh_from_db()
    assert doc.tipo_id == tipo_b.id
    assert not DocumentoProcesso.objects.filter(processo=processo).exclude(pk=doc.pk).exists()


@pytest.mark.django_db
def test_editar_processo_documentos_action_salva_ordem_e_tipo_em_lote(client):
    processo = _create_processo()
    tipo_a = _create_tipo_documento("TIPO A", processo.tipo_pagamento)
    tipo_b = _create_tipo_documento("TIPO B", processo.tipo_pagamento)
    tipo_lote = _create_tipo_documento("TIPO LOTE", processo.tipo_pagamento)
    doc_1 = _add_documento(processo, tipo_a, 1, "doc_1.pdf")
    doc_2 = _add_documento(processo, tipo_b, 2, "doc_2.pdf")

    user = _create_backoffice_user()
    client.force_login(user)
    response = client.post(
        reverse("editar_processo_documentos_action", kwargs={"pk": processo.id}),
        data={
            "documento-TOTAL_FORMS": "2",
            "documento-INITIAL_FORMS": "2",
            "documento-MIN_NUM_FORMS": "0",
            "documento-MAX_NUM_FORMS": "1000",
            "documento-0-id": str(doc_1.id),
            "documento-0-tipo": str(tipo_lote.id),
            "documento-0-ordem": "2",
            "documento-1-id": str(doc_2.id),
            "documento-1-tipo": str(tipo_lote.id),
            "documento-1-ordem": "1",
            "next": "",
        },
        secure=True,
    )

    assert response.status_code == 302
    doc_1.refresh_from_db()
    doc_2.refresh_from_db()
    assert doc_1.ordem == 2
    assert doc_2.ordem == 1
    assert doc_1.tipo_id == tipo_lote.id
    assert doc_2.tipo_id == tipo_lote.id


@pytest.mark.django_db
def test_extrair_codigo_barras_documento_action_persiste_boleto(client, monkeypatch):
    processo = _create_processo()
    tipo_boleto = _create_tipo_documento("BOLETO BANCARIO", processo.tipo_pagamento)
    documento = _add_documento(processo, tipo_boleto, 1, "boleto.pdf")
    user = _create_backoffice_user()
    client.force_login(user)

    monkeypatch.setattr(
        cadastro_actions,
        "processar_pdf_boleto",
        lambda _arquivo: {"codigo_barras": "34191790010104351004791020150008291070000010000"},
    )
    response = client.post(
        reverse(
            "extrair_codigo_barras_documento_action",
            kwargs={"pk": processo.id, "documento_id": documento.id},
        ),
        secure=True,
    )

    assert response.status_code == 302
    boleto = Boleto_Bancario.objects.get(pk=documento.id)
    assert boleto.codigo_barras == "34191790010104351004791020150008291070000010000"


@pytest.mark.django_db
def test_extrair_codigo_barras_documento_action_ignora_documento_nao_boleto(client, monkeypatch):
    processo = _create_processo()
    tipo_outro = _create_tipo_documento("OUTRO", processo.tipo_pagamento)
    documento = _add_documento(processo, tipo_outro, 1, "outro.pdf")
    user = _create_backoffice_user()
    client.force_login(user)

    monkeypatch.setattr(
        cadastro_actions,
        "processar_pdf_boleto",
        lambda _arquivo: {"codigo_barras": "34191790010104351004791020150008291070000010000"},
    )
    response = client.post(
        reverse(
            "extrair_codigo_barras_documento_action",
            kwargs={"pk": processo.id, "documento_id": documento.id},
        ),
        follow=True,
        secure=True,
    )

    assert response.status_code == 200
    assert not Boleto_Bancario.objects.filter(processo=processo).exists()
    assert "Extração permitida apenas para documentos do tipo BOLETO BANCÁRIO." in response.content.decode("utf-8")


@pytest.mark.django_db
def test_editar_processo_documentos_view_renderiza_widgets_padrao(client):
    processo = _create_processo()
    tipo_outro = _create_tipo_documento("OUTRO", processo.tipo_pagamento)
    _add_documento(processo, tipo_outro, 1, "outro.pdf")
    user = _create_backoffice_user()
    client.force_login(user)

    response = client.get(reverse("editar_processo_documentos", kwargs={"pk": processo.id}), secure=True)

    html = response.content.decode("utf-8")
    assert response.status_code == 200
    assert 'id="document-list-documento"' in html
    assert 'id="batch-doc-type-documento"' in html
    assert 'id="document-preview-widget-documento"' in html
    assert "drag-handle" in html
    assert "Extrair código de barras" not in html


@pytest.mark.django_db
def test_editar_processo_documentos_view_mostra_botao_extracao_para_boleto(client):
    processo = _create_processo()
    tipo_boleto = _create_tipo_documento("BOLETO BANCÁRIO", processo.tipo_pagamento)
    _add_documento(processo, tipo_boleto, 1, "boleto.pdf")
    user = _create_backoffice_user()
    client.force_login(user)

    response = client.get(reverse("editar_processo_documentos", kwargs={"pk": processo.id}), secure=True)

    html = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "Extrair código de barras" in html


@pytest.mark.django_db
def test_extrair_codigos_barras_lote_processa_todos_boletos(client, monkeypatch):
    processo = _create_processo()
    tipo_boleto = _create_tipo_documento("BOLETO BANCÁRIO", processo.tipo_pagamento)
    tipo_outro = _create_tipo_documento("OUTRO", processo.tipo_pagamento)
    _add_documento(processo, tipo_boleto, 1, "boleto1.pdf")
    _add_documento(processo, tipo_boleto, 2, "boleto2.pdf")
    _add_documento(processo, tipo_outro, 3, "contrato.pdf")
    user = _create_backoffice_user()
    client.force_login(user)

    monkeypatch.setattr(
        cadastro_actions,
        "processar_pdf_boleto",
        lambda _arquivo: {"codigo_barras": "34191790010104351004791020150008291070000010000"},
    )
    response = client.post(
        reverse("extrair_codigos_barras_lote_action", kwargs={"pk": processo.id}),
        follow=True,
        secure=True,
    )

    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "2 boleto(s) processado(s)" in html
    assert "2 extraído(s) com sucesso" in html
    assert "0 falha(s)" in html
    assert Boleto_Bancario.objects.filter(processo=processo).count() == 2


@pytest.mark.django_db
def test_extrair_codigos_barras_lote_sem_boletos_emite_aviso(client):
    processo = _create_processo()
    tipo_outro = _create_tipo_documento("OUTRO", processo.tipo_pagamento)
    _add_documento(processo, tipo_outro, 1, "contrato.pdf")
    user = _create_backoffice_user()
    client.force_login(user)

    response = client.post(
        reverse("extrair_codigos_barras_lote_action", kwargs={"pk": processo.id}),
        follow=True,
        secure=True,
    )

    assert response.status_code == 200
    assert "Nenhum documento do tipo BOLETO BANCÁRIO" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_extrair_codigos_barras_lote_contabiliza_falhas(client, monkeypatch):
    processo = _create_processo()
    tipo_boleto = _create_tipo_documento("BOLETO BANCÁRIO", processo.tipo_pagamento)
    _add_documento(processo, tipo_boleto, 1, "boleto1.pdf")
    _add_documento(processo, tipo_boleto, 2, "boleto2.pdf")
    user = _create_backoffice_user()
    client.force_login(user)

    call_count = {"n": 0}

    def extrator_parcial(_arquivo):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"codigo_barras": "34191790010104351004791020150008291070000010000"}
        raise ValueError("PDF inválido")

    monkeypatch.setattr(cadastro_actions, "processar_pdf_boleto", extrator_parcial)

    response = client.post(
        reverse("extrair_codigos_barras_lote_action", kwargs={"pk": processo.id}),
        follow=True,
        secure=True,
    )

    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "2 boleto(s) processado(s)" in html
    assert "1 extraído(s) com sucesso" in html
    assert "1 falha(s)" in html
