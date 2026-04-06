"""High-level matching strategy tests for SISCAC sync and comprovantes flows."""

import contextlib
import io
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase

from processos.models.segments.documents import ComprovanteDePagamento
from processos.models.segments.cadastros import ContasBancarias, Credor
from processos.models.segments.core import Processo
from processos.models.segments.parametrizations import StatusChoicesProcesso
from processos.utils import processar_pdf_comprovantes
from processos.views.fluxo.siscac_processo_sync import sync_siscac_payments


class SiscacSyncDecisionMatrixTest(TestCase):
    """Validates success/divergence/orphan classification in SISCAC reconciliation."""

    def test_sync_siscac_payments_classifies_matrix_consistently(self):
        status_pago = StatusChoicesProcesso.objects.create(status_choice="PAGO - EM CONFERÊNCIA")

        credor_ok = Credor.objects.create(nome="Empresa Alfa Ltda", cpf_cnpj="11.111.111/0001-11")
        credor_div = Credor.objects.create(nome="Fornecedor Beta", cpf_cnpj="22.222.222/0001-22")
        credor_orphan = Credor.objects.create(nome="Sem Retorno SISCAC", cpf_cnpj="33.333.333/0001-33")

        processo_sucesso = Processo.objects.create(
            status=status_pago,
            credor=credor_ok,
            n_nota_empenho="2026NE00001",
            valor_liquido=Decimal("100.00"),
            n_pagamento_siscac="2025PG00001",
        )
        ComprovanteDePagamento.objects.create(processo=processo_sucesso, numero_comprovante="COMP-123")

        processo_divergente = Processo.objects.create(
            status=status_pago,
            credor=credor_div,
            n_nota_empenho="2026NE00001",
            valor_liquido=Decimal("200.00"),
            n_pagamento_siscac=None,
        )
        ComprovanteDePagamento.objects.create(processo=processo_divergente, numero_comprovante="COMP-123")

        processo_orfao = Processo.objects.create(
            status=status_pago,
            credor=credor_orphan,
            n_nota_empenho="2026NE00099",
            valor_liquido=Decimal("50.00"),
            n_pagamento_siscac="",
        )

        extracted = [
            {
                "comprovante": "COMP-123",
                "nota_empenho": "2026NE00001",
                "credor": "Empresa Alfa",
                "valor_total": Decimal("100.00"),
                "siscac_pg": "2026PG99999",
            }
        ]

        resultados = sync_siscac_payments(extracted)

        self.assertEqual(len(resultados["sucessos"]), 1)
        self.assertEqual(resultados["sucessos"][0]["id"], processo_sucesso.id)
        self.assertEqual(resultados["retroativos_corrigidos"], 1)

        processo_sucesso.refresh_from_db()
        self.assertEqual(processo_sucesso.n_pagamento_siscac, "2026PG99999")

        self.assertEqual(len(resultados["divergencias"]), 1)
        self.assertEqual(resultados["divergencias"][0]["processo_id"], processo_divergente.id)

        orphan_ids = {item["id"] for item in resultados["nao_encontrados"]}
        self.assertIn(processo_orfao.id, orphan_ids)


class ComprovanteIdentityPrecedenceTest(TestCase):
    """Ensures comprovante identity prefers CPF/CNPJ over account fallback."""

    @patch("processos.utils.pdfplumber.open")
    @patch("processos.utils.default_storage.open")
    @patch("processos.utils.split_pdf_to_temp_pages")
    def test_doc_match_has_precedence_over_account_match(
        self,
        mock_split,
        mock_storage_open,
        mock_pdfplumber_open,
    ):
        credor_doc = Credor.objects.create(nome="Credor por Documento", cpf_cnpj="11.222.333/0001-44")
        credor_conta = Credor.objects.create(nome="Credor por Conta", cpf_cnpj="55.666.777/0001-88")
        ContasBancarias.objects.create(
            titular=credor_conta,
            banco="341",
            agencia="1234-5",
            conta="98765-0",
        )

        mock_split.return_value = [{"temp_path": "temp/teste.pdf", "url": "/media/temp/teste.pdf", "pagina": 1}]

        @contextlib.contextmanager
        def _fake_storage_open(*args, **kwargs):
            yield io.BytesIO(b"%PDF-1.4")

        mock_storage_open.side_effect = _fake_storage_open

        texto = (
            "COMPROVANTE DE PAGAMENTO "
            "CNPJ FAVORECIDO: 11.222.333/0001-44 "
            "AGENCIA: 1234-5 CONTA: 98.765-0 "
            "VALOR TOTAL: 1.000,00 "
            "DATA DO PAGAMENTO: 10/03/2026 "
            "NR.AUTENTICACAO A.123.456.789.012.345"
        )
        fake_page = MagicMock()
        fake_page.extract_text.return_value = texto
        fake_pdf = MagicMock()
        fake_pdf.pages = [fake_page]
        fake_pdf_cm = MagicMock()
        fake_pdf_cm.__enter__.return_value = fake_pdf
        fake_pdf_cm.__exit__.return_value = False
        mock_pdfplumber_open.return_value = fake_pdf_cm

        pdf_file = io.BytesIO(b"fake")
        pdf_file.name = "comprovante.pdf"
        resultados = processar_pdf_comprovantes(pdf_file)

        self.assertEqual(len(resultados), 1)
        r = resultados[0]

        self.assertEqual(r["credor_extraido"], credor_doc.nome)
        self.assertEqual(r["data_pagamento"], "2026-03-10")
        self.assertAlmostEqual(r["valor_extraido"], 1000.0)

        docs = {item["doc"]: item["credor"] for item in r["documentos_encontrados"]}
        self.assertEqual(docs.get("11.222.333/0001-44"), credor_doc)

        contas = {(item["agencia"], item["conta"]): item["credor"] for item in r["contas_encontradas"]}
        self.assertEqual(contas.get(("1234-5", "98765-0")), credor_conta)
