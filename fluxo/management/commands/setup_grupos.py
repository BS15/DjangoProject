from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from fluxo.domain_models import Processo


GRUPOS_PERMISSOES = {
    "FUNCIONARIO(A) CONTAS A PAGAR": [
        "acesso_backoffice",
        "pode_operar_contas_pagar",
        "pode_aprovar_contingencia_supervisor",
        "pode_arquivar",
    ],
    "FISCAL DE CONTRATO": ["acesso_backoffice", "pode_atestar_liquidacao"],
    "ORDENADOR(A) DE DESPESA": ["acesso_backoffice", "pode_autorizar_pagamento"],
    "CONTADOR(A)": ["acesso_backoffice", "pode_contabilizar"],
    "CONSELHEIRO(A) FISCAL": ["acesso_backoffice", "pode_auditar_conselho"],
    "GESTOR(A) DE VERBAS - CONSULTA": ["acesso_backoffice", "pode_visualizar_verbas"],
    "GESTOR(A) DE VERBAS - DIARIAS": [
        "acesso_backoffice",
        "pode_visualizar_verbas",
        "pode_criar_diarias",
        "pode_importar_diarias",
        "pode_gerenciar_diarias",
        "pode_autorizar_diarias",
        "pode_agrupar_verbas",
        "pode_gerenciar_processos_verbas",
        "pode_sincronizar_diarias_siscac",
    ],
    "GESTOR(A) DE VERBAS - REEMBOLSOS": [
        "acesso_backoffice",
        "pode_visualizar_verbas",
        "pode_gerenciar_reembolsos",
        "pode_agrupar_verbas",
        "pode_gerenciar_processos_verbas",
    ],
    "GESTOR(A) DE VERBAS - JETONS": [
        "acesso_backoffice",
        "pode_visualizar_verbas",
        "pode_gerenciar_jetons",
        "pode_agrupar_verbas",
        "pode_gerenciar_processos_verbas",
    ],
    "GESTOR(A) DE VERBAS - AUXILIOS": [
        "acesso_backoffice",
        "pode_visualizar_verbas",
        "pode_gerenciar_auxilios",
        "pode_agrupar_verbas",
        "pode_gerenciar_processos_verbas",
    ],
}


class Command(BaseCommand):
    help = "Cria grupos e vincula permissoes customizadas do dominio fluxo."

    def handle(self, *args, **options):
        content_type = ContentType.objects.get_for_model(Processo)

        for nome_grupo, codenames in GRUPOS_PERMISSOES.items():
            grupo, created = Group.objects.get_or_create(name=nome_grupo)
            if created:
                self.stdout.write(f'Grupo criado: "{nome_grupo}"')
            else:
                self.stdout.write(f'Grupo existente: "{nome_grupo}" (resetando permissoes)')

            grupo.permissions.clear()

            for codename in codenames:
                try:
                    permissao = Permission.objects.get(codename=codename, content_type=content_type)
                    grupo.permissions.add(permissao)
                    self.stdout.write(f'  + {codename}')
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'  ! Permissao ausente: {codename}'))

        self.stdout.write(self.style.SUCCESS("Grupos e permissoes configurados com sucesso."))
