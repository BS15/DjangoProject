from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from processos.models.fluxo import Processo


GRUPOS_PERMISSOES = {
    'Operacional (Contas a Pagar)': ['acesso_backoffice', 'pode_operar_contas_pagar'],
    'Fiscais (Atestadores)': ['acesso_backoffice', 'pode_atestar_liquidacao'],
    'Ordenadores de Despesa': ['acesso_backoffice', 'pode_autorizar_pagamento'],
    'Contabilidade': ['acesso_backoffice', 'pode_contabilizar'],
    'Conselho Fiscal': ['acesso_backoffice', 'pode_auditar_conselho'],
}


class Command(BaseCommand):
    help = 'Cria os grupos de usuários e atribui as permissões personalizadas do sistema.'

    def handle(self, *args, **options):
        # All custom RBAC permissions are defined on the Processo model (see migration 0053).
        content_type = ContentType.objects.get_for_model(Processo)

        for nome_grupo, codenames in GRUPOS_PERMISSOES.items():
            grupo, created = Group.objects.get_or_create(name=nome_grupo)

            if created:
                self.stdout.write(f'  Grupo criado: "{nome_grupo}"')
            else:
                self.stdout.write(f'  Grupo já existe: "{nome_grupo}" — limpando permissões anteriores.')

            grupo.permissions.clear()

            for codename in codenames:
                try:
                    permissao = Permission.objects.get(codename=codename, content_type=content_type)
                    grupo.permissions.add(permissao)
                    self.stdout.write(f'    + Permissão adicionada: "{codename}"')
                except Permission.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f'    ⚠ Permissão não encontrada no banco: "{codename}" '
                            f'(execute as migrações pendentes e tente novamente)'
                        )
                    )

        self.stdout.write(self.style.SUCCESS('\n✔  Grupos e permissões configurados com sucesso.'))
