from datetime import date

from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse

from processos.models import Credor, Processo, ReembolsoCombustivel
from processos.views import (
    add_auxilio_view,
    add_diaria_view,
    add_jeton_view,
    add_reembolso_view,
    agrupar_verbas_view,
    auxilios_list_view,
    diarias_list_view,
    edit_auxilio_view,
    edit_jeton_view,
    edit_reembolso_view,
    jetons_list_view,
    reembolsos_list_view,
)


class VerbasSplitRoutingTest(TestCase):
    def test_rotas_principais_verbas_apontam_para_views_exportadas(self):
        casos = [
            ('diarias_list', diarias_list_view),
            ('reembolsos_list', reembolsos_list_view),
            ('jetons_list', jetons_list_view),
            ('auxilios_list', auxilios_list_view),
            ('add_diaria', add_diaria_view),
            ('add_reembolso', add_reembolso_view),
            ('add_jeton', add_jeton_view),
            ('add_auxilio', add_auxilio_view),
        ]

        for nome_url, view_esperada in casos:
            with self.subTest(url_name=nome_url):
                match = resolve(reverse(nome_url))
                self.assertIs(match.func, view_esperada)

    def test_rotas_edicao_verbas_apontam_para_views_exportadas(self):
        casos = [
            ('edit_reembolso', {'pk': 1}, edit_reembolso_view),
            ('edit_jeton', {'pk': 1}, edit_jeton_view),
            ('edit_auxilio', {'pk': 1}, edit_auxilio_view),
        ]

        for nome_url, kwargs, view_esperada in casos:
            with self.subTest(url_name=nome_url):
                match = resolve(reverse(nome_url, kwargs=kwargs))
                self.assertIs(match.func, view_esperada)


class AgrupamentoVerbasRuleTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.beneficiario_a = Credor.objects.create(nome='Beneficiario A', tipo='PF')
        self.beneficiario_b = Credor.objects.create(nome='Beneficiario B', tipo='PF')

    def _request_post_com_sessao(self, url, data):
        request = self.factory.post(url, data=data)
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        request.user = AnonymousUser()
        request._messages = FallbackStorage(request)
        return request

    def _novo_reembolso(self, beneficiario, numero):
        return ReembolsoCombustivel.objects.create(
            numero_sequencial=str(numero),
            beneficiario=beneficiario,
            data_saida=date(2026, 1, 10),
            data_retorno=date(2026, 1, 11),
            cidade_origem='Brasilia',
            cidade_destino='Goiania',
            distancia_km='100.00',
            preco_combustivel='6.00',
            valor_total='120.00',
        )

    def test_agrupar_multiplos_beneficiarios_define_credor_banco_do_brasil(self):
        reembolso_1 = self._novo_reembolso(self.beneficiario_a, 1)
        reembolso_2 = self._novo_reembolso(self.beneficiario_b, 2)

        url = reverse('agrupar_verbas', kwargs={'tipo_verba': 'reembolso'})
        request = self._request_post_com_sessao(
            url,
            {'verbas_selecionadas': [str(reembolso_1.id), str(reembolso_2.id)]},
        )

        response = agrupar_verbas_view(request, 'reembolso')

        self.assertEqual(response.status_code, 302)
        processo = Processo.objects.latest('id')
        self.assertEqual(processo.credor.nome, 'BANCO DO BRASIL S/A')

        reembolso_1.refresh_from_db()
        reembolso_2.refresh_from_db()
        self.assertEqual(reembolso_1.processo_id, processo.id)
        self.assertEqual(reembolso_2.processo_id, processo.id)

    def test_agrupar_mesmo_beneficiario_mantem_credor_original(self):
        reembolso_1 = self._novo_reembolso(self.beneficiario_a, 3)
        reembolso_2 = self._novo_reembolso(self.beneficiario_a, 4)

        url = reverse('agrupar_verbas', kwargs={'tipo_verba': 'reembolso'})
        request = self._request_post_com_sessao(
            url,
            {'verbas_selecionadas': [str(reembolso_1.id), str(reembolso_2.id)]},
        )

        response = agrupar_verbas_view(request, 'reembolso')

        self.assertEqual(response.status_code, 302)
        processo = Processo.objects.latest('id')
        self.assertEqual(processo.credor_id, self.beneficiario_a.id)
