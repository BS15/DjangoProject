from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from processos.services import document_workflow


@contextmanager
def _fake_open(binary_content):
    """Context manager that mimics Django FileField.open()."""
    yield SimpleNamespace(read=lambda: binary_content)


class DocumentWorkflowServiceTest(SimpleTestCase):
    def test_construir_signatarios_padrao_inclui_campos_multiplos_e_remove_duplicados(self):
        entidade = SimpleNamespace(
            beneficiario=SimpleNamespace(email="benef@example.com"),
            proponente=SimpleNamespace(email="prop@example.com"),
            credor=SimpleNamespace(email="benef@example.com"),
            solicitante=SimpleNamespace(email="req@example.com"),
            aprovado_por_ordenador=SimpleNamespace(email="ord@example.com"),
        )

        signatarios = document_workflow.construir_signatarios_padrao(
            entidade,
            extra_emails=["extra@example.com", "prop@example.com", ""],
        )

        self.assertEqual(
            signatarios,
            [
                {"email": "benef@example.com", "action": "SIGN"},
                {"email": "prop@example.com", "action": "SIGN"},
                {"email": "req@example.com", "action": "SIGN"},
                {"email": "ord@example.com", "action": "SIGN"},
                {"email": "extra@example.com", "action": "SIGN"},
            ],
        )

    def test_montar_resposta_pdf_com_buffer(self):
        pdf_buffer = SimpleNamespace(read=lambda: b"%PDF-test", seek=lambda *_: None)

        response = document_workflow.montar_resposta_pdf(pdf_buffer, "arquivo.pdf", inline=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn('inline; filename="arquivo.pdf"', response["Content-Disposition"])
        self.assertEqual(response.content, b"%PDF-test")

    @patch("processos.services.document_workflow.gerar_documento_bytes", return_value=b"%PDF-bytes")
    def test_gerar_resposta_pdf_usa_geracao_padrao(self, gerar_bytes_mock):
        response = document_workflow.gerar_resposta_pdf("pcd", object(), "doc.pdf")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"%PDF-bytes")
        gerar_bytes_mock.assert_called_once()

    @patch("processos.autentique_service.enviar_documento_para_assinatura")
    def test_disparar_assinatura_rascunho_le_arquivo_e_envia(self, enviar_mock):
        enviar_mock.return_value = {"id": "doc-99", "url": "http://link", "signers_data": {"a@x.com": {"short_link": "http://s"}}}

        assinatura = SimpleNamespace(
            id=9,
            tipo_documento="SCD",
            arquivo=SimpleNamespace(open=lambda mode: _fake_open(b"%PDF-raw")),
            save=MagicMock(),
        )

        document_workflow.disparar_assinatura_rascunho(
            assinatura,
            signatarios=[{"email": "a@x.com", "action": "SIGN"}],
            nome_doc="SCD_9",
        )

        enviar_mock.assert_called_once_with(
            b"%PDF-raw",
            "SCD_9",
            [{"email": "a@x.com", "action": "SIGN"}],
        )
        self.assertEqual(assinatura.autentique_id, "doc-99")
        self.assertEqual(assinatura.status, "PENDENTE")
        assinatura.save.assert_called_once()

    @patch("processos.services.document_workflow.disparar_assinatura_rascunho")
    @patch("processos.services.document_workflow.construir_signatarios_padrao")
    def test_disparar_assinatura_rascunho_com_signatarios_resolve_e_dispara(
        self,
        construir_signatarios_mock,
        disparar_mock,
    ):
        assinatura = SimpleNamespace(
            id=17,
            tipo_documento="PCD",
            entidade_relacionada=SimpleNamespace(id=1),
        )
        signatarios = [{"email": "assinante@example.com", "action": "SIGN"}]
        construir_signatarios_mock.return_value = signatarios

        document_workflow.disparar_assinatura_rascunho_com_signatarios(assinatura)

        construir_signatarios_mock.assert_called_once_with(assinatura.entidade_relacionada)
        disparar_mock.assert_called_once_with(assinatura, signatarios, nome_doc="PCD_17")

    def test_disparar_assinatura_rascunho_com_signatarios_sem_entidade_retorna_none(self):
        assinatura = SimpleNamespace(
            id=11,
            tipo_documento="SCD",
            entidade_relacionada=None,
        )

        resultado = document_workflow.disparar_assinatura_rascunho_com_signatarios(assinatura)
        self.assertIsNone(resultado)

    @patch("processos.services.document_workflow.construir_signatarios_padrao", return_value=[])
    def test_disparar_assinatura_rascunho_com_signatarios_sem_signatarios_retorna_none(
        self,
        _construir_signatarios_mock,
    ):
        assinatura = SimpleNamespace(
            id=12,
            tipo_documento="SCD",
            entidade_relacionada=SimpleNamespace(id=2),
        )

        resultado = document_workflow.disparar_assinatura_rascunho_com_signatarios(assinatura)
        self.assertIsNone(resultado)

    @patch("processos.autentique_service.verificar_e_baixar_documento")
    def test_sincronizar_assinatura_quando_assinado_atualiza_arquivo(self, verificar_mock):
        verificar_mock.return_value = {"assinado": True, "pdf_bytes": b"%PDF-signed"}

        arquivo_assinado = MagicMock()
        assinatura = SimpleNamespace(
            id=3,
            tipo_documento="PCD",
            status="PENDENTE",
            autentique_id="abc-123",
            arquivo_assinado=arquivo_assinado,
            save=MagicMock(),
        )

        resultado = document_workflow.sincronizar_assinatura(assinatura)

        self.assertEqual(resultado, "signed")
        arquivo_assinado.save.assert_called_once()
        assinatura.save.assert_called_once()

    @patch("processos.autentique_service.verificar_e_baixar_documento")
    def test_sincronizar_assinatura_quando_pendente_retorna_pending(self, verificar_mock):
        verificar_mock.return_value = {"assinado": False, "pdf_bytes": None}

        assinatura = SimpleNamespace(
            id=10,
            tipo_documento="SCD",
            status="PENDENTE",
            autentique_id="xyz-999",
            arquivo_assinado=MagicMock(),
            save=MagicMock(),
        )

        resultado = document_workflow.sincronizar_assinatura(assinatura)

        self.assertEqual(resultado, "pending")
        assinatura.save.assert_not_called()

    @patch("processos.models.segments.auxiliary.AssinaturaAutentique")
    @patch("processos.services.document_workflow.ContentType")
    @patch("processos.autentique_service.enviar_documento_para_assinatura")
    @patch("processos.services.document_workflow.gerar_documento_bytes", return_value=b"%PDF-generated")
    def test_enviar_para_assinatura_gera_pdf_quando_pdf_bytes_nao_informado(
        self,
        gerar_bytes_mock,
        enviar_mock,
        content_type_mock,
        assinatura_model_mock,
    ):
        enviar_mock.return_value = {"id": "new-doc-99", "url": "http://link", "signers_data": {}}
        ct_instance = MagicMock()
        content_type_mock.objects.get_for_model.return_value = ct_instance
        assinatura_model_mock.objects.filter.return_value.first.return_value = None

        entidade = SimpleNamespace(pk=42)
        signatarios = [{"email": "assinante@example.com", "action": "SIGN"}]

        document_workflow.enviar_para_assinatura(
            entidade=entidade,
            tipo_documento="SCD",
            nome_doc="SCD_42",
            signatarios=signatarios,
            doc_type="scd",
            numero_reuniao=2,
        )

        gerar_bytes_mock.assert_called_once_with("scd", entidade, numero_reuniao=2)
        enviar_mock.assert_called_once_with(b"%PDF-generated", "SCD_42", signatarios)
        assinatura_model_mock.objects.create.assert_called_once_with(
            content_type=ct_instance,
            object_id=42,
            tipo_documento="SCD",
            autentique_id="new-doc-99",
            autentique_url="http://link",
            dados_signatarios={},
            status="PENDENTE",
        )

    def test_sincronizar_assinatura_quando_ja_assinado_retorna_already_signed(self):
        assinatura = SimpleNamespace(
            id=77,
            tipo_documento="PCD",
            status="ASSINADO",
            autentique_id="signed-77",
            arquivo_assinado=MagicMock(),
            save=MagicMock(),
        )

        resultado = document_workflow.sincronizar_assinatura(assinatura)

        self.assertEqual(resultado, "already_signed")
        assinatura.save.assert_not_called()
