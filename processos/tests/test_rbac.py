"""
RBAC security tests.

Verifies that:
1. Unauthenticated requests are redirected to the login page by
   GlobalLoginRequiredMiddleware.
2. Authenticated users without the required permission receive 403 Forbidden
   (raise_exception=True on all @permission_required decorators).
3. Authenticated users WITH the correct permission can access the views
   (responses are 200 or an application-level redirect, never a 403/302-to-login).
"""

from django.contrib.auth.models import User, Permission
from django.test import TestCase, override_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(username, password='testpass123'):
    return User.objects.create_user(username=username, password=password)


def _grant(user, codename):
    perm = Permission.objects.get(codename=codename)
    user.user_permissions.add(perm)
    # Flush the cached permission set so the new perm is visible immediately.
    user._perm_cache = set()
    user._user_perm_cache = set()


# ---------------------------------------------------------------------------
# Middleware: unauthenticated requests must be redirected to login
# ---------------------------------------------------------------------------

@override_settings(SECURE_SSL_REDIRECT=False)
class GlobalLoginMiddlewareTest(TestCase):
    """Unauthenticated users must be redirected to the login page."""

    PROTECTED_URLS = [
        '/',
        '/processos/contabilizacao/',
        '/processos/conselho/',
        '/processos/autorizacao/',
        '/processos/conferencia/',
        '/processos/arquivamento/',
        '/auditoria/',
        '/relatorios/',
    ]

    def test_unauthenticated_redirected_to_login(self):
        for url in self.PROTECTED_URLS:
            with self.subTest(url=url):
                response = self.client.get(url)
                # Middleware issues a 302 redirect to the login page.
                self.assertEqual(
                    response.status_code, 302,
                    f"Expected 302 for unauthenticated {url}, got {response.status_code}",
                )
                self.assertIn('/accounts/login/', response['Location'])

    def test_login_page_accessible_without_auth(self):
        response = self.client.get('/accounts/login/')
        # Login page itself must be reachable (not caught by middleware).
        self.assertIn(response.status_code, (200, 301, 302))


# ---------------------------------------------------------------------------
# Permission-required views: authenticated but unprivileged → 403
# ---------------------------------------------------------------------------

@override_settings(SECURE_SSL_REDIRECT=False)
class PermissionDeniedTest(TestCase):
    """Authenticated users without the required permission get 403."""

    def setUp(self):
        self.user = _make_user('noperm')
        self.client.login(username='noperm', password='testpass123')

    # --- Contabilização ---

    def test_painel_contabilizacao_403(self):
        response = self.client.get('/processos/contabilizacao/')
        self.assertEqual(response.status_code, 403)

    def test_iniciar_contabilizacao_403(self):
        response = self.client.get('/processos/contabilizacao/iniciar/')
        self.assertEqual(response.status_code, 403)

    # --- Conselho Fiscal ---

    def test_painel_conselho_403(self):
        response = self.client.get('/processos/conselho/')
        self.assertEqual(response.status_code, 403)

    def test_iniciar_conselho_reuniao_403(self):
        response = self.client.get('/processos/conselho/reunioes/1/iniciar/')
        self.assertEqual(response.status_code, 403)

    def test_gerenciar_reunioes_403(self):
        response = self.client.get('/processos/conselho/reunioes/')
        self.assertEqual(response.status_code, 403)

    # --- Autorização de Pagamento ---

    def test_painel_autorizacao_403(self):
        response = self.client.get('/processos/autorizacao/')
        self.assertEqual(response.status_code, 403)

    # --- Contas a Pagar / Conferência ---

    def test_painel_conferencia_403(self):
        response = self.client.get('/processos/conferencia/')
        self.assertEqual(response.status_code, 403)

    def test_iniciar_conferencia_403(self):
        response = self.client.get('/processos/conferencia/iniciar/')
        self.assertEqual(response.status_code, 403)

    def test_contas_a_pagar_403(self):
        response = self.client.get('/contas-a-pagar/')
        self.assertEqual(response.status_code, 403)

    def test_a_empenhar_403(self):
        response = self.client.get('/a-empenhar/')
        self.assertEqual(response.status_code, 403)

    # --- Arquivamento ---

    def test_painel_arquivamento_403(self):
        response = self.client.get('/processos/arquivamento/')
        self.assertEqual(response.status_code, 403)

    # --- Backoffice (add/edit process) ---

    def test_add_process_403(self):
        response = self.client.get('/adicionar/')
        self.assertEqual(response.status_code, 403)

    # --- Banking ---

    def test_lancamento_bancario_403(self):
        response = self.client.get('/processos/lancamento-bancario/')
        self.assertEqual(response.status_code, 403)

    # --- Verbas indenizatórias ---

    def test_verbas_panel_403(self):
        response = self.client.get('/verbas/')
        self.assertEqual(response.status_code, 403)

    def test_diarias_list_403(self):
        response = self.client.get('/verbas/diarias/')
        self.assertEqual(response.status_code, 403)

    def test_add_diaria_403(self):
        response = self.client.get('/verbas/diarias/nova/')
        self.assertEqual(response.status_code, 403)

    def test_importar_diarias_403(self):
        response = self.client.get('/verbas/diarias/importar/')
        self.assertEqual(response.status_code, 403)

    def test_painel_autorizacao_diarias_403(self):
        response = self.client.get('/verbas/diarias/autorizacao/')
        self.assertEqual(response.status_code, 403)

    def test_sincronizar_diarias_403(self):
        response = self.client.get('/verbas/sincronizar-diarias/')
        self.assertEqual(response.status_code, 403)

    def test_sincronizar_siscac_403(self):
        response = self.client.get('/fluxo/sincronizar-siscac/')
        self.assertEqual(response.status_code, 403)


@override_settings(SECURE_SSL_REDIRECT=False)
class DebugOnlyRoutesTest(TestCase):
    def setUp(self):
        self.user = _make_user('debugcheck')
        self.client.login(username='debugcheck', password='testpass123')

    def test_dev_and_test_routes_absent_when_not_debug(self):
        for url in (
            '/dados-fake/',
            '/testes/pdfs/',
            '/ferramentas/chaos-testing/',
            '/processo/1/gerar-dummy-pdf/',
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Permission-required views: privileged user can access
# ---------------------------------------------------------------------------

@override_settings(SECURE_SSL_REDIRECT=False)
class PrivilegedAccessTest(TestCase):
    """Authenticated users WITH the required permission can access the view."""

    def _login_with_perm(self, codename):
        user = _make_user(f'user_{codename}')
        _grant(user, codename)
        self.client.login(username=f'user_{codename}', password='testpass123')
        return user

    def test_painel_contabilizacao_allowed(self):
        self._login_with_perm('pode_contabilizar')
        response = self.client.get('/processos/contabilizacao/')
        self.assertNotEqual(response.status_code, 403)
        self.assertNotIn('/accounts/login/', response.get('Location', ''))

    def test_painel_conselho_allowed(self):
        self._login_with_perm('pode_auditar_conselho')
        response = self.client.get('/processos/conselho/')
        self.assertNotEqual(response.status_code, 403)
        self.assertNotIn('/accounts/login/', response.get('Location', ''))

    def test_painel_autorizacao_allowed(self):
        self._login_with_perm('pode_autorizar_pagamento')
        response = self.client.get('/processos/autorizacao/')
        self.assertNotEqual(response.status_code, 403)
        self.assertNotIn('/accounts/login/', response.get('Location', ''))

    def test_painel_conferencia_allowed(self):
        self._login_with_perm('pode_operar_contas_pagar')
        response = self.client.get('/processos/conferencia/')
        self.assertNotEqual(response.status_code, 403)
        self.assertNotIn('/accounts/login/', response.get('Location', ''))

    def test_painel_arquivamento_allowed(self):
        self._login_with_perm('pode_arquivar')
        response = self.client.get('/processos/arquivamento/')
        self.assertNotEqual(response.status_code, 403)
        self.assertNotIn('/accounts/login/', response.get('Location', ''))

    def test_add_process_allowed(self):
        self._login_with_perm('acesso_backoffice')
        response = self.client.get('/adicionar/')
        self.assertNotEqual(response.status_code, 403)
        self.assertNotIn('/accounts/login/', response.get('Location', ''))

    def test_contas_a_pagar_allowed(self):
        self._login_with_perm('pode_operar_contas_pagar')
        response = self.client.get('/contas-a-pagar/')
        self.assertNotEqual(response.status_code, 403)
        self.assertNotIn('/accounts/login/', response.get('Location', ''))

    def test_verbas_panel_allowed(self):
        self._login_with_perm('pode_visualizar_verbas')
        response = self.client.get('/verbas/')
        self.assertNotEqual(response.status_code, 403)
        self.assertNotIn('/accounts/login/', response.get('Location', ''))

    def test_add_diaria_allowed(self):
        self._login_with_perm('pode_criar_diarias')
        response = self.client.get('/verbas/diarias/nova/')
        self.assertNotEqual(response.status_code, 403)
        self.assertNotIn('/accounts/login/', response.get('Location', ''))

    def test_importar_diarias_allowed(self):
        self._login_with_perm('pode_importar_diarias')
        response = self.client.get('/verbas/diarias/importar/')
        self.assertNotEqual(response.status_code, 403)
        self.assertNotIn('/accounts/login/', response.get('Location', ''))

    def test_painel_autorizacao_diarias_allowed(self):
        self._login_with_perm('pode_autorizar_diarias')
        response = self.client.get('/verbas/diarias/autorizacao/')
        self.assertNotEqual(response.status_code, 403)
        self.assertNotIn('/accounts/login/', response.get('Location', ''))

    def test_sincronizar_diarias_allowed(self):
        self._login_with_perm('pode_sincronizar_diarias_siscac')
        response = self.client.get('/verbas/sincronizar-diarias/')
        self.assertNotEqual(response.status_code, 403)
        self.assertNotIn('/accounts/login/', response.get('Location', ''))

    def test_sincronizar_siscac_allowed(self):
        self._login_with_perm('pode_operar_contas_pagar')
        response = self.client.get('/fluxo/sincronizar-siscac/')
        self.assertNotEqual(response.status_code, 403)
        self.assertNotIn('/accounts/login/', response.get('Location', ''))
