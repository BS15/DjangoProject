from django.test import TestCase
from .invoice_processor import process_invoice_taxes, _normalizar_cidade


class NormalizarCidadeTest(TestCase):
    def test_remove_acentos(self):
        self.assertEqual(_normalizar_cidade("Florianópolis"), "FLORIANOPOLIS")

    def test_uppercase(self):
        self.assertEqual(_normalizar_cidade("joinville"), "JOINVILLE")

    def test_string_vazia(self):
        self.assertEqual(_normalizar_cidade(""), "")

    def test_none(self):
        self.assertEqual(_normalizar_cidade(None), "")


class ProcessInvoiceTaxesSimpleNacionalTest(TestCase):
    """Optante pelo Simples Nacional: impostos federais são ignorados."""

    def _base_json(self):
        return {
            "valor_bruto": 1000.00,
            "valor_liquido": 1000.00,
            "optante_simples_nacional": True,
            "impostos_federais": {"ir": 94.0, "pis": 0.0, "cofins": 0.0, "csll": 0.0},
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": 0.0, "local_prestacao_servico": ""},
            "inss_destacado": 0.0,
        }

    def test_sem_retencoes_federais(self):
        resultado = process_invoice_taxes(self._base_json())
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertNotIn("6190", codigos)
        self.assertNotIn("6147", codigos)

    def test_sucesso_matematico(self):
        resultado = process_invoice_taxes(self._base_json())
        self.assertTrue(resultado["sucesso_matematico"])

    def test_sem_alertas(self):
        resultado = process_invoice_taxes(self._base_json())
        self.assertEqual(resultado["alertas_usuario"], [])


class ProcessInvoiceTaxesFederaisTest(TestCase):
    """Não optante – validação dos códigos de impostos federais."""

    def _json_com_aliquota(self, soma_federais, valor_bruto=1000.00):
        return {
            "valor_bruto": valor_bruto,
            "valor_liquido": valor_bruto - soma_federais,
            "optante_simples_nacional": False,
            "impostos_federais": {
                "ir": soma_federais,
                "pis": 0.0,
                "cofins": 0.0,
                "csll": 0.0,
            },
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": 0.0, "local_prestacao_servico": ""},
            "inss_destacado": 0.0,
        }

    def test_codigo_6190(self):
        # 9.45% → entre 9.40 e 9.50
        resultado = process_invoice_taxes(self._json_com_aliquota(94.50))
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertIn("6190", codigos)

    def test_codigo_6147(self):
        # 5.85% → entre 5.80 e 5.90
        resultado = process_invoice_taxes(self._json_com_aliquota(58.50))
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertIn("6147", codigos)

    def test_aliquota_fora_dos_intervalos(self):
        # 10% → nenhum código reconhecido
        resultado = process_invoice_taxes(self._json_com_aliquota(100.0))
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertNotIn("6190", codigos)
        self.assertNotIn("6147", codigos)

    def test_alerta_sem_impostos_sem_justificativa(self):
        data = self._json_com_aliquota(0.0)
        data["valor_liquido"] = 1000.00
        resultado = process_invoice_taxes(data)
        self.assertTrue(any("impostos federais" in a for a in resultado["alertas_usuario"]))

    def test_sem_alerta_com_justificativa(self):
        data = self._json_com_aliquota(0.0)
        data["valor_liquido"] = 1000.00
        data["justificativa_isencao_federal"] = "Imune por decisão judicial"
        resultado = process_invoice_taxes(data)
        self.assertFalse(any("impostos federais" in a for a in resultado["alertas_usuario"]))


class ProcessInvoiceTaxesISSTest(TestCase):
    """Validação das regras de ISS municipal."""

    def _json_iss(self, valor, cidade):
        return {
            "valor_bruto": 1000.00,
            "valor_liquido": 1000.00 - valor,
            "optante_simples_nacional": True,
            "impostos_federais": {"ir": 0.0, "pis": 0.0, "cofins": 0.0, "csll": 0.0},
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": valor, "local_prestacao_servico": cidade},
            "inss_destacado": 0.0,
        }

    def test_cidade_conveniada_gera_retencao(self):
        resultado = process_invoice_taxes(self._json_iss(50.0, "Florianópolis"))
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertIn("ISS_RETIDO", codigos)

    def test_cidade_nao_conveniada_gera_alerta(self):
        resultado = process_invoice_taxes(self._json_iss(50.0, "São Paulo"))
        self.assertFalse(
            any(r["codigo"] == "ISS_RETIDO" for r in resultado["retencoes_a_processar"])
        )
        self.assertTrue(any("não conveniada" in a for a in resultado["alertas_usuario"]))

    def test_cidade_uppercase_sem_acento(self):
        resultado = process_invoice_taxes(self._json_iss(30.0, "BALNEARIO CAMBORIU"))
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertIn("ISS_RETIDO", codigos)

    def test_iss_zero_sem_retencao(self):
        resultado = process_invoice_taxes(self._json_iss(0.0, "Joinville"))
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertNotIn("ISS_RETIDO", codigos)


class ProcessInvoiceTaxesINSSTest(TestCase):
    """Validação das regras de INSS."""

    def _json_inss(self, valor):
        return {
            "valor_bruto": 1000.00,
            "valor_liquido": 1000.00 - valor,
            "optante_simples_nacional": True,
            "impostos_federais": {"ir": 0.0, "pis": 0.0, "cofins": 0.0, "csll": 0.0},
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": 0.0, "local_prestacao_servico": ""},
            "inss_destacado": valor,
        }

    def test_inss_destacado_gera_retencao(self):
        resultado = process_invoice_taxes(self._json_inss(110.0))
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertIn("INSS_RETIDO", codigos)

    def test_inss_destacado_gera_alerta_informativo(self):
        resultado = process_invoice_taxes(self._json_inss(110.0))
        self.assertTrue(any("INSS" in a for a in resultado["alertas_usuario"]))

    def test_inss_zero_sem_retencao(self):
        resultado = process_invoice_taxes(self._json_inss(0.0))
        codigos = [r["codigo"] for r in resultado["retencoes_a_processar"]]
        self.assertNotIn("INSS_RETIDO", codigos)


class ProcessInvoiceTaxesMathCheckTest(TestCase):
    """Verificação matemática de integridade."""

    def test_nota_fechada_sucesso(self):
        data = {
            "valor_bruto": 1000.00,
            "valor_liquido": 905.50,
            "optante_simples_nacional": False,
            "impostos_federais": {"ir": 94.50, "pis": 0.0, "cofins": 0.0, "csll": 0.0},
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": 0.0, "local_prestacao_servico": ""},
            "inss_destacado": 0.0,
        }
        resultado = process_invoice_taxes(data)
        self.assertTrue(resultado["sucesso_matematico"])
        self.assertFalse(any("integridade" in a for a in resultado["alertas_usuario"]))

    def test_nota_com_divergencia_gera_alerta(self):
        data = {
            "valor_bruto": 1000.00,
            "valor_liquido": 800.00,   # Divergência proposital
            "optante_simples_nacional": False,
            "impostos_federais": {"ir": 94.50, "pis": 0.0, "cofins": 0.0, "csll": 0.0},
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": 0.0, "local_prestacao_servico": ""},
            "inss_destacado": 0.0,
        }
        resultado = process_invoice_taxes(data)
        self.assertFalse(resultado["sucesso_matematico"])
        self.assertTrue(any("integridade" in a for a in resultado["alertas_usuario"]))

    def test_tolerancia_centavos(self):
        # diferença de 0.03 deve ser aceita
        data = {
            "valor_bruto": 1000.00,
            "valor_liquido": 905.47,
            "optante_simples_nacional": False,
            "impostos_federais": {"ir": 94.50, "pis": 0.0, "cofins": 0.0, "csll": 0.0},
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": 0.0, "local_prestacao_servico": ""},
            "inss_destacado": 0.0,
        }
        resultado = process_invoice_taxes(data)
        self.assertTrue(resultado["sucesso_matematico"])


class ProcessInvoiceTaxesOutputContractTest(TestCase):
    """Verifica o contrato de saída da função."""

    def test_chaves_obrigatorias(self):
        data = {
            "valor_bruto": 500.0,
            "valor_liquido": 500.0,
            "optante_simples_nacional": True,
            "impostos_federais": {"ir": 0.0, "pis": 0.0, "cofins": 0.0, "csll": 0.0},
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": 0.0, "local_prestacao_servico": ""},
            "inss_destacado": 0.0,
        }
        resultado = process_invoice_taxes(data)
        self.assertIn("sucesso_matematico", resultado)
        self.assertIn("valor_bruto_identificado", resultado)
        self.assertIn("valor_liquido_identificado", resultado)
        self.assertIn("retencoes_a_processar", resultado)
        self.assertIn("alertas_usuario", resultado)

    def test_retencoes_tem_campos_corretos(self):
        data = {
            "valor_bruto": 1000.00,
            "valor_liquido": 905.50,
            "optante_simples_nacional": False,
            "impostos_federais": {"ir": 94.50, "pis": 0.0, "cofins": 0.0, "csll": 0.0},
            "justificativa_isencao_federal": None,
            "iss": {"valor_destacado": 0.0, "local_prestacao_servico": ""},
            "inss_destacado": 0.0,
        }
        resultado = process_invoice_taxes(data)
        for retencao in resultado["retencoes_a_processar"]:
            self.assertIn("codigo", retencao)
            self.assertIn("valor", retencao)
            self.assertIn("descricao", retencao)

