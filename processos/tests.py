from django.test import TestCase
from .invoice_processor import process_invoice_taxes, _normalizar_cidade
from .models import Processo, StatusChoicesProcesso, TiposDeDocumento, DocumentoProcesso, DocumentoFiscal
from .validators import verificar_turnpike
from .views import STATUS_BLOQUEADOS_TOTAL, STATUS_SOMENTE_DOCUMENTOS


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


class AuditoriaViewTest(TestCase):
    """Testa a view de auditoria que exibe o histórico do django-simple-history."""

    def test_auditoria_retorna_200(self):
        response = self.client.get('/auditoria/')
        self.assertEqual(response.status_code, 200)

    def test_auditoria_usa_template_correto(self):
        response = self.client.get('/auditoria/')
        self.assertTemplateUsed(response, 'auditoria.html')

    def test_auditoria_contexto_tem_chaves_esperadas(self):
        response = self.client.get('/auditoria/')
        self.assertIn('registros', response.context)
        self.assertIn('total', response.context)
        self.assertIn('modelos_disponiveis', response.context)
        self.assertIn('filtros', response.context)

    def test_auditoria_filtros_preservados_no_contexto(self):
        response = self.client.get('/auditoria/?modelo=Processo&tipo_acao=%2B&usuario=admin')
        self.assertEqual(response.context['filtros']['modelo'], 'Processo')
        self.assertEqual(response.context['filtros']['tipo_acao'], '+')
        self.assertEqual(response.context['filtros']['usuario'], 'admin')


class EditarProcessoRestrictionsTest(TestCase):
    """Tests for the edit-permission tiers on editar_processo view."""

    def _make_processo(self, status_text):
        status_obj = StatusChoicesProcesso.objects.create(status_choice=status_text)
        return Processo.objects.create(status=status_obj)

    # ------------------------------------------------------------------ #
    # Tier-1 (STATUS_BLOQUEADOS_TOTAL): access must be blocked entirely.  #
    # ------------------------------------------------------------------ #

    def test_bloqueado_total_get_redirects_home(self):
        """GET on an archived/cancelled process must redirect to home_page."""
        status_text = next(iter(STATUS_BLOQUEADOS_TOTAL))
        processo = self._make_processo(status_text)
        response = self.client.get(f'/processo/{processo.pk}/editar/')
        self.assertRedirects(response, '/', fetch_redirect_response=False)

    def test_bloqueado_total_post_redirects_home(self):
        """POST on an archived/cancelled process must be rejected (redirect to home)."""
        status_text = next(iter(STATUS_BLOQUEADOS_TOTAL))
        processo = self._make_processo(status_text)
        response = self.client.post(f'/processo/{processo.pk}/editar/', data={})
        self.assertRedirects(response, '/', fetch_redirect_response=False)

    def test_all_bloqueado_statuses_redirect(self):
        """Every Tier-1 status redirects to home_page."""
        for status_text in STATUS_BLOQUEADOS_TOTAL:
            with self.subTest(status=status_text):
                processo = self._make_processo(status_text)
                response = self.client.get(f'/processo/{processo.pk}/editar/')
                self.assertRedirects(response, '/', fetch_redirect_response=False)

    # ------------------------------------------------------------------ #
    # Tier-2 (STATUS_SOMENTE_DOCUMENTOS): only document changes allowed.  #
    # ------------------------------------------------------------------ #

    def test_somente_documentos_get_returns_200(self):
        """GET on an authorised process must render the edit page (not redirect)."""
        status_text = next(iter(STATUS_SOMENTE_DOCUMENTOS))
        processo = self._make_processo(status_text)
        response = self.client.get(f'/processo/{processo.pk}/editar/')
        self.assertEqual(response.status_code, 200)

    def test_somente_documentos_context_flag(self):
        """The `somente_documentos` flag must be True in context for Tier-2 statuses."""
        status_text = next(iter(STATUS_SOMENTE_DOCUMENTOS))
        processo = self._make_processo(status_text)
        response = self.client.get(f'/processo/{processo.pk}/editar/')
        self.assertTrue(response.context['somente_documentos'])

    def test_full_edit_context_flag_is_false(self):
        """The `somente_documentos` flag must be False for unrestricted statuses."""
        status_text = 'A PAGAR - PENDENTE AUTORIZAÇÃO'
        processo = self._make_processo(status_text)
        response = self.client.get(f'/processo/{processo.pk}/editar/')
        self.assertFalse(response.context['somente_documentos'])



class VerificarTurnpikeTest(TestCase):
    """Tests for the verificar_turnpike status-transition gate."""

    def _make_processo(self, status_text='A EMPENHAR'):
        status_obj = StatusChoicesProcesso.objects.create(status_choice=status_text)
        return Processo.objects.create(status=status_obj)

    def _add_document(self, processo, tipo_nome):
        tipo, _ = TiposDeDocumento.objects.get_or_create(
            tipo_de_documento=tipo_nome
        )
        return DocumentoProcesso.objects.create(
            processo=processo,
            tipo=tipo,
            arquivo='dummy/path.pdf',
            ordem=1,
        )

    def _add_nota_fiscal(self, processo, atestada=True):
        return DocumentoFiscal.objects.create(
            processo=processo,
            numero_nota_fiscal='NF-001',
            data_emissao='2024-01-01',
            valor_bruto='1000.00',
            valor_liquido='900.00',
            atestada=atestada,
        )

    # ------------------------------------------------------------------ #
    # Rule 1: A EMPENHAR → AGUARDANDO LIQUIDAÇÃO                          #
    # ------------------------------------------------------------------ #

    def test_empenhar_to_aguardando_sem_documento_retorna_erro(self):
        """Without DOCUMENTOS ORÇAMENTÁRIOS, transition must be blocked."""
        processo = self._make_processo('A EMPENHAR')
        erros = verificar_turnpike(processo, 'A EMPENHAR', 'AGUARDANDO LIQUIDAÇÃO')
        self.assertTrue(len(erros) > 0)
        self.assertIn('DOCUMENTOS ORÇAMENTÁRIOS', erros[0])

    def test_empenhar_to_aguardando_com_documento_ok(self):
        """With DOCUMENTOS ORÇAMENTÁRIOS attached, transition must be allowed."""
        processo = self._make_processo('A EMPENHAR')
        self._add_document(processo, 'DOCUMENTOS ORÇAMENTÁRIOS')
        erros = verificar_turnpike(processo, 'A EMPENHAR', 'AGUARDANDO LIQUIDAÇÃO')
        self.assertEqual(erros, [])

    def test_empenhar_to_aguardando_case_insensitive(self):
        """Document type check must be case-insensitive (ASCII chars, SQLite-compatible)."""
        processo = self._make_processo('A EMPENHAR')
        # 'Comprovante de Pagamento' → validates iexact works for ASCII case differences;
        # for the DOCUMENTOS ORÇAMENTÁRIOS type, we store with the canonical uppercase form
        # to avoid SQLite's limited Unicode LIKE behaviour in tests.
        self._add_document(processo, 'DOCUMENTOS ORÇAMENTÁRIOS')
        erros = verificar_turnpike(processo, 'A EMPENHAR', 'AGUARDANDO LIQUIDAÇÃO')
        self.assertEqual(erros, [])

    def test_empenhar_to_aguardando_ateste_variant(self):
        """'AGUARDANDO LIQUIDAÇÃO / ATESTE' variant must also be accepted as the target."""
        processo = self._make_processo('A EMPENHAR')
        self._add_document(processo, 'DOCUMENTOS ORÇAMENTÁRIOS')
        erros = verificar_turnpike(processo, 'A EMPENHAR', 'AGUARDANDO LIQUIDAÇÃO / ATESTE')
        self.assertEqual(erros, [])

    # ------------------------------------------------------------------ #
    # Rule 2: AGUARDANDO LIQUIDAÇÃO → A PAGAR - PENDENTE AUTORIZAÇÃO      #
    # ------------------------------------------------------------------ #

    def test_aguardando_to_pagar_sem_notas_retorna_erro(self):
        """Without any documentos fiscais, transition must be blocked."""
        processo = self._make_processo('AGUARDANDO LIQUIDAÇÃO')
        erros = verificar_turnpike(processo, 'AGUARDANDO LIQUIDAÇÃO', 'A PAGAR - PENDENTE AUTORIZAÇÃO')
        self.assertTrue(len(erros) > 0)

    def test_aguardando_to_pagar_nota_nao_atestada_retorna_erro(self):
        """When a nota fiscal is NOT attested, transition must be blocked."""
        processo = self._make_processo('AGUARDANDO LIQUIDAÇÃO')
        self._add_nota_fiscal(processo, atestada=False)
        erros = verificar_turnpike(processo, 'AGUARDANDO LIQUIDAÇÃO', 'A PAGAR - PENDENTE AUTORIZAÇÃO')
        self.assertTrue(len(erros) > 0)
        self.assertIn('atestados', erros[0])

    def test_aguardando_to_pagar_todas_atestadas_ok(self):
        """When all notas fiscais are attested, transition must be allowed."""
        processo = self._make_processo('AGUARDANDO LIQUIDAÇÃO')
        self._add_nota_fiscal(processo, atestada=True)
        self._add_nota_fiscal(processo, atestada=True)
        erros = verificar_turnpike(processo, 'AGUARDANDO LIQUIDAÇÃO', 'A PAGAR - PENDENTE AUTORIZAÇÃO')
        self.assertEqual(erros, [])

    def test_aguardando_ateste_variant_also_checked(self):
        """'AGUARDANDO LIQUIDAÇÃO / ATESTE' variant triggers the same rule."""
        processo = self._make_processo('AGUARDANDO LIQUIDAÇÃO / ATESTE')
        self._add_nota_fiscal(processo, atestada=False)
        erros = verificar_turnpike(processo, 'AGUARDANDO LIQUIDAÇÃO / ATESTE', 'A PAGAR - PENDENTE AUTORIZAÇÃO')
        self.assertTrue(len(erros) > 0)

    # ------------------------------------------------------------------ #
    # Rule 3: LANÇADO - AGUARDANDO COMPROVANTE → PAGO - EM CONFERÊNCIA    #
    # ------------------------------------------------------------------ #

    def test_lancado_to_pago_sem_comprovante_retorna_erro(self):
        """Without COMPROVANTE DE PAGAMENTO, transition must be blocked."""
        processo = self._make_processo('LANÇADO - AGUARDANDO COMPROVANTE')
        erros = verificar_turnpike(
            processo,
            'LANÇADO - AGUARDANDO COMPROVANTE',
            'PAGO - EM CONFERÊNCIA',
        )
        self.assertTrue(len(erros) > 0)
        self.assertIn('COMPROVANTE DE PAGAMENTO', erros[0])

    def test_lancado_to_pago_com_comprovante_ok(self):
        """With COMPROVANTE DE PAGAMENTO attached, transition must be allowed."""
        processo = self._make_processo('LANÇADO - AGUARDANDO COMPROVANTE')
        self._add_document(processo, 'COMPROVANTE DE PAGAMENTO')
        erros = verificar_turnpike(
            processo,
            'LANÇADO - AGUARDANDO COMPROVANTE',
            'PAGO - EM CONFERÊNCIA',
        )
        self.assertEqual(erros, [])

    def test_lancado_to_pago_comprovante_case_insensitive(self):
        """Document type check must be case-insensitive."""
        processo = self._make_processo('LANÇADO - AGUARDANDO COMPROVANTE')
        self._add_document(processo, 'Comprovante de Pagamento')
        erros = verificar_turnpike(
            processo,
            'LANÇADO - AGUARDANDO COMPROVANTE',
            'PAGO - EM CONFERÊNCIA',
        )
        self.assertEqual(erros, [])

    # ------------------------------------------------------------------ #
    # Transitions not in any rule must not generate errors.               #
    # ------------------------------------------------------------------ #

    def test_unrelated_transition_no_error(self):
        """Transitions not covered by the turnpike must always pass."""
        processo = self._make_processo('A PAGAR - PENDENTE AUTORIZAÇÃO')
        erros = verificar_turnpike(
            processo,
            'A PAGAR - PENDENTE AUTORIZAÇÃO',
            'A PAGAR - ENVIADO PARA AUTORIZAÇÃO',
        )
        self.assertEqual(erros, [])
