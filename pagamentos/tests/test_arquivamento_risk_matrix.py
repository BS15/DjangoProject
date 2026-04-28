import io

import pytest

from pagamentos.domain_models import ProcessoStatus
from pagamentos.views.helpers.archival import _executar_arquivamento_definitivo
from pagamentos.views.helpers.errors import ArquivamentoDefinitivoError, ArquivamentoSemDocumentosError

_STATUS_FIELD = "opcao_status"


class _BufferComFalhaLeitura:
    def read(self):
        raise OSError("Falha de leitura em storage cloud")


@pytest.mark.django_db
def test_arquivamento_falha_sem_documentos_validos(processo_factory, user_factory):
    processo = processo_factory(status=ProcessoStatus.APROVADO_PENDENTE_ARQUIVAMENTO)
    with pytest.raises(ArquivamentoSemDocumentosError):
        _executar_arquivamento_definitivo(processo, user_factory("arq_sem_docs"))


@pytest.mark.django_db
def test_arquivamento_aborta_quando_consolidado_tem_zero_bytes(monkeypatch, processo_factory, user_factory):
    processo = processo_factory(status=ProcessoStatus.APROVADO_PENDENTE_ARQUIVAMENTO)
    monkeypatch.setattr(
        "pagamentos.views.helpers.archival.gerar_pdf_consolidado_processo",
        lambda _processo: io.BytesIO(b""),
    )

    with pytest.raises(ArquivamentoDefinitivoError):
        _executar_arquivamento_definitivo(processo, user_factory("arq_zero"))

    processo.refresh_from_db()
    assert not processo.arquivo_final
    assert processo.status.opcao_status == ProcessoStatus.APROVADO_PENDENTE_ARQUIVAMENTO


@pytest.mark.django_db(transaction=True)
def test_arquivamento_aborta_em_falha_de_leitura_cloud(monkeypatch, processo_factory, user_factory):
    processo = processo_factory(status=ProcessoStatus.APROVADO_PENDENTE_ARQUIVAMENTO)
    monkeypatch.setattr(
        "pagamentos.views.helpers.archival.gerar_pdf_consolidado_processo",
        lambda _processo: _BufferComFalhaLeitura(),
    )

    with pytest.raises(ArquivamentoDefinitivoError):
        _executar_arquivamento_definitivo(processo, user_factory("arq_cloud_fail"))

    processo.refresh_from_db()
    assert not processo.arquivo_final
    assert processo.status.opcao_status == ProcessoStatus.APROVADO_PENDENTE_ARQUIVAMENTO


@pytest.mark.django_db(transaction=True)
def test_arquivamento_rollback_mid_flight_ao_falhar_avanco_de_status(
    monkeypatch,
    processo_factory,
    user_factory,
    pdf_bytes,
):
    processo = processo_factory(status=ProcessoStatus.APROVADO_PENDENTE_ARQUIVAMENTO)
    monkeypatch.setattr(
        "pagamentos.views.helpers.archival.gerar_pdf_consolidado_processo",
        lambda _processo: io.BytesIO(pdf_bytes),
    )

    def _falhar_avanco(*args, **kwargs):
        """Simula falha no avanço de status para validar rollback transacional."""
        raise RuntimeError("Falha no avanço de status")

    monkeypatch.setattr(type(processo), "avancar_status", _falhar_avanco)

    with pytest.raises(RuntimeError):
        _executar_arquivamento_definitivo(processo, user_factory("arq_midflight"))

    processo.refresh_from_db()
    assert not processo.arquivo_final
    assert processo.status.opcao_status == ProcessoStatus.APROVADO_PENDENTE_ARQUIVAMENTO
