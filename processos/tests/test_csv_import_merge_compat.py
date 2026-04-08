from io import BytesIO
from unittest.mock import patch

from django.test import SimpleTestCase

from processos.utils import confirmar_diarias_lote, importar_contas_fixas_csv, importar_credores_csv, preview_diarias_lote
from processos.utils.csv_common import build_csv_dict_reader
from processos.utils.verbas.diarias.importacao import _open_diaria_csv


class CsvCommonHelperTest(SimpleTestCase):
    def test_build_reader_accepts_latin1_when_configured(self):
        csv_file = BytesIO('NOME,CPF_CNPJ\nJoão,123\n'.encode('latin-1'))

        reader, erro = build_csv_dict_reader(
            csv_file,
            encodings=('utf-8-sig', 'latin-1'),
            encoding_error_message='erro',
        )

        self.assertIsNone(erro)
        self.assertIsNotNone(reader)
        rows = list(reader)
        self.assertEqual(rows[0]['NOME'], 'João')

    def test_build_reader_rejects_non_utf8_when_strict(self):
        csv_file = BytesIO('NOME,CPF_CNPJ\nJoão,123\n'.encode('latin-1'))

        reader, erro = build_csv_dict_reader(
            csv_file,
            encodings=('utf-8',),
            encoding_error_message='utf8-only',
        )

        self.assertIsNone(reader)
        self.assertEqual(erro, 'utf8-only')


class DiariasCsvOpenTest(SimpleTestCase):
    def test_open_diaria_csv_reporta_colunas_ausentes(self):
        csv_file = BytesIO('NOME_BENEFICIARIO,DATA_SAIDA\nFulano,01/01/2026\n'.encode('utf-8'))

        reader, erro = _open_diaria_csv(csv_file)

        self.assertIsNone(reader)
        self.assertIsNotNone(erro)
        self.assertIn('Cabeçalho inválido. Colunas ausentes:', erro)


class ImportApiCompatibilityTest(SimpleTestCase):
    def test_public_exports_remain_available(self):
        self.assertTrue(callable(importar_credores_csv))
        self.assertTrue(callable(importar_contas_fixas_csv))
        self.assertTrue(callable(preview_diarias_lote))
        self.assertTrue(callable(confirmar_diarias_lote))

    @patch('processos.utils.cadastros_import.build_csv_dict_reader')
    def test_importar_credores_usa_reader_compartilhado(self, mocked_builder):
        class EmptyReader:
            line_num = 1

            def __iter__(self):
                return iter(())

        mocked_builder.return_value = (EmptyReader(), None)

        resultado = importar_credores_csv(BytesIO(b'NOME,CPF_CNPJ\n'))

        self.assertEqual(resultado, {'sucessos': 0, 'erros': []})
        mocked_builder.assert_called_once()

    @patch('processos.utils.cadastros_import.build_csv_dict_reader')
    def test_importar_contas_usa_reader_compartilhado(self, mocked_builder):
        class EmptyReader:
            line_num = 1

            def __iter__(self):
                return iter(())

        mocked_builder.return_value = (EmptyReader(), None)

        resultado = importar_contas_fixas_csv(BytesIO(b'NOME_CREDOR,DIA_VENCIMENTO,DETALHAMENTO\n'))

        self.assertEqual(resultado, {'sucessos': 0, 'erros': []})
        mocked_builder.assert_called_once()
