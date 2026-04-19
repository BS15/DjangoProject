import io
import uuid
from unittest.mock import Mock

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from pypdf import PdfReader, PdfWriter

from credores.models import Credor
from pagamentos.domain_models import (
    Boleto_Bancario,
    DocumentoProcesso,
    FormasDePagamento,
    Processo,
    ProcessoStatus,
    StatusChoicesProcesso,
    TiposDeDocumento,
    TiposDePagamento,
)
from pagamentos.services import processo_documentos
from pagamentos.services.processo_documentos import (
    DocumentoGeradoDuplicadoError,
    gerar_documentos_automaticos_processo,
    gerar_e_anexar_documento_processo,
    gerar_pdf_consolidado_processo,
    _nomes_documentais_equivalentes,
)
from commons.shared.pdf_tools import mesclar_pdfs_em_memoria


def _gerar_pdf_bytes(paginas=1):
    writer = PdfWriter()
    for _ in range(paginas):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class FakeCloudStorage:
    def __init__(self, arquivos):
        self.arquivos = arquivos

    def exists(self, name):
        return name in self.arquivos

    def open(self, name, mode="rb"):
        if "r" not in mode:
            raise NotImplementedError("FakeCloudStorage suporta apenas leitura nos testes.")
        if name not in self.arquivos:
            raise FileNotFoundError(name)
        return io.BytesIO(self.arquivos[name])

    def path(self, name):
        raise NotImplementedError("Cloud storage não expõe caminho local.")


@pytest.fixture
def pdf_bytes():
    return _gerar_pdf_bytes()


@pytest.fixture
def processo_factory(db):
    def factory(*, status=ProcessoStatus.A_PAGAR_AUTORIZADO, forma_nome="PIX", tipo_nome="SERVIÇO"):
        credor = Credor.objects.create(
            nome=f"Credor {uuid.uuid4().hex[:6]}",
            cpf_cnpj="12345678901",
            tipo="PF",
        )
        forma_pagamento = FormasDePagamento.objects.create(
            forma_de_pagamento=f"{forma_nome} {uuid.uuid4().hex[:6]}"
        )
        tipo_pagamento = TiposDePagamento.objects.create(
            tipo_de_pagamento=f"{tipo_nome} {uuid.uuid4().hex[:6]}"
        )
        status_obj, _ = StatusChoicesProcesso.objects.get_or_create(
            status_choice__iexact=status,
            defaults={"status_choice": status},
        )
        return Processo.objects.create(
            credor=credor,
            valor_bruto="100.00",
            valor_liquido="100.00",
            forma_pagamento=forma_pagamento,
            tipo_pagamento=tipo_pagamento,
            status=status_obj,
        )

    return factory


@pytest.fixture
def tipo_documento_factory(db):
    def factory(nome, *, tipo_pagamento=None):
        return TiposDeDocumento.objects.create(
            tipo_de_documento=f"{nome} {uuid.uuid4().hex[:6]}",
            tipo_de_pagamento=tipo_pagamento,
        )

    return factory


@pytest.mark.django_db
def test_documento_processo_generico_nao_cria_especializacao_boleto(processo_factory, tipo_documento_factory, pdf_bytes):
    processo = processo_factory()
    tipo_documento = tipo_documento_factory("DOCUMENTO GENÉRICO")

    documento = DocumentoProcesso.objects.create(
        processo=processo,
        tipo=tipo_documento,
        ordem=1,
        arquivo=ContentFile(pdf_bytes, name="generico.pdf"),
    )

    assert DocumentoProcesso.objects.filter(pk=documento.pk).exists()
    assert Boleto_Bancario.objects.count() == 0

    with pytest.raises(Boleto_Bancario.DoesNotExist):
        _ = documento.boleto_bancario


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("novo_status", "documentos_esperados"),
    [
        (
            ProcessoStatus.A_PAGAR_AUTORIZADO,
            [
                (
                    "TERMO DE AUTORIZAÇÃO DE PAGAMENTO",
                    "Termo_Autorizacao_Proc_{processo_id}.pdf",
                )
            ],
        ),
        (
            ProcessoStatus.CONTABILIZADO_CONSELHO,
            [
                ("TERMO DE CONTABILIZAÇÃO", "Termo_Contabilizacao_Proc_{processo_id}.pdf"),
                ("TERMO DE AUDITORIA", "Termo_Auditoria_Proc_{processo_id}.pdf"),
            ],
        ),
    ],
)
def test_gerar_documentos_automaticos_processo_gera_documentos_esperados(
    monkeypatch,
    processo_factory,
    pdf_bytes,
    novo_status,
    documentos_esperados,
):
    processo = processo_factory(status=ProcessoStatus.A_PAGAR_ENVIADO_PARA_AUTORIZACAO)
    mock_integracao = Mock()

    monkeypatch.setattr(processo_documentos, "gerar_documento_bytes", lambda *args, **kwargs: pdf_bytes)
    monkeypatch.setattr(processo_documentos, "gerar_documentos_relacionados_por_transicao", mock_integracao)

    gerar_documentos_automaticos_processo(
        processo,
        ProcessoStatus.A_PAGAR_ENVIADO_PARA_AUTORIZACAO,
        novo_status,
    )

    documentos = list(processo.documentos.select_related("tipo").order_by("ordem"))
    assert len(documentos) == len(documentos_esperados)
    assert [documento.ordem for documento in documentos] == list(range(1, len(documentos) + 1))

    for documento, (tipo_esperado, nome_esperado) in zip(documentos, documentos_esperados):
        assert documento.tipo.tipo_de_documento == tipo_esperado
        assert _nomes_documentais_equivalentes(
            documento.arquivo.name,
            nome_esperado.format(processo_id=processo.id),
        )

    mock_integracao.assert_called_once_with(
        processo,
        ProcessoStatus.A_PAGAR_ENVIADO_PARA_AUTORIZACAO,
        novo_status,
    )


@pytest.mark.django_db
def test_gerar_e_anexar_documento_processo_lanca_erro_em_nome_duplicado(monkeypatch, processo_factory, pdf_bytes):
    processo = processo_factory()
    monkeypatch.setattr(processo_documentos, "gerar_documento_bytes", lambda *args, **kwargs: pdf_bytes)

    gerar_e_anexar_documento_processo(
        processo,
        "autorizacao",
        processo,
        f"Termo_Autorizacao_Proc_{processo.id}.pdf",
        "TERMO DE AUTORIZAÇÃO DE PAGAMENTO",
    )

    with pytest.raises(DocumentoGeradoDuplicadoError):
        gerar_e_anexar_documento_processo(
            processo,
            "autorizacao",
            processo,
            f"Termo_Autorizacao_Proc_{processo.id}.pdf",
            "TERMO DE AUTORIZAÇÃO DE PAGAMENTO",
        )


@pytest.mark.django_db
def test_gerar_documentos_automaticos_processo_eh_idempotente_para_mesma_transicao(
    monkeypatch,
    processo_factory,
    pdf_bytes,
):
    processo = processo_factory(status=ProcessoStatus.A_PAGAR_ENVIADO_PARA_AUTORIZACAO)
    monkeypatch.setattr(processo_documentos, "gerar_documento_bytes", lambda *args, **kwargs: pdf_bytes)
    monkeypatch.setattr(processo_documentos, "gerar_documentos_relacionados_por_transicao", Mock())

    gerar_documentos_automaticos_processo(
        processo,
        ProcessoStatus.A_PAGAR_ENVIADO_PARA_AUTORIZACAO,
        ProcessoStatus.A_PAGAR_AUTORIZADO,
    )
    gerar_documentos_automaticos_processo(
        processo,
        ProcessoStatus.A_PAGAR_ENVIADO_PARA_AUTORIZACAO,
        ProcessoStatus.A_PAGAR_AUTORIZADO,
    )

    assert processo.documentos.count() == 1


@pytest.mark.django_db
def test_gerar_pdf_consolidado_processo_usa_storage_cloud_sem_path(
    monkeypatch,
    processo_factory,
):
    processo = processo_factory()
    tipo_documento = TiposDeDocumento.objects.create(tipo_de_documento=f"PDF CLOUD {uuid.uuid4().hex[:6]}")
    pdf_a = _gerar_pdf_bytes()
    pdf_b = _gerar_pdf_bytes()

    DocumentoProcesso.objects.create(
        processo=processo,
        tipo=tipo_documento,
        ordem=1,
        arquivo="cloud/doc-1.pdf",
    )
    DocumentoProcesso.objects.create(
        processo=processo,
        tipo=tipo_documento,
        ordem=2,
        arquivo="cloud/doc-2.pdf",
    )

    fake_storage = FakeCloudStorage({
        "cloud/doc-1.pdf": pdf_a,
        "cloud/doc-2.pdf": pdf_b,
    })
    monkeypatch.setattr(default_storage, "_wrapped", fake_storage)

    consolidado = gerar_pdf_consolidado_processo(processo)

    assert consolidado is not None
    assert len(PdfReader(consolidado).pages) == 2


def test_mesclar_pdfs_em_memoria_aceita_bytes_sem_caminho_local(pdf_bytes):
    consolidado = mesclar_pdfs_em_memoria([pdf_bytes, pdf_bytes])

    assert len(PdfReader(consolidado).pages) == 2