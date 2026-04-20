from __future__ import annotations

import unicodedata

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from pagamentos.domain_models import FormasDePagamento, Processo, TiposDeDocumento, TiposDePagamento


FORMAS_PAGAMENTO_CANONICAS = [
    "GERENCIADOR/BOLETO BANCÁRIO",
    "TRANSFERÊNCIA (TED)",
    "PIX",
    "REMESSA BANCÁRIA",
    "CARTÃO PRÉ-PAGO",
]

TIPOS_PAGAMENTO_CANONICOS = [
    "CONTAS FIXAS",
    "IMPOSTOS",
    "VERBAS INDENIZATÓRIAS",
    "REMUNERAÇÃO",
    "SUPRIMENTO DE FUNDOS",
]

DOCUMENTOS_CONTAS_FIXAS_CANONICOS = [
    "BOLETO BANCÁRIO",
    "NOTA FISCAL (NF)",
    "DOCUMENTOS ORÇAMENTÁRIOS",
    "FATURA",
    "RELATÓRIO",
    "ORDEM DE COMPRA (OC)",
]

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


def _normalizar_rotulo(valor: str) -> str:
    """Normaliza texto para comparação sem acentos e case-insensitive."""
    sem_acentos = "".join(
        ch for ch in unicodedata.normalize("NFKD", valor or "") if not unicodedata.combining(ch)
    )
    return " ".join(sem_acentos.upper().split())


class Command(BaseCommand):
    help = "Executa setup headstart de catálogos financeiros e grupos/permissões."

    @transaction.atomic
    def handle(self, *args, **options):
        formas_criadas = 0
        formas_atualizadas = 0
        tipos_criados = 0
        tipos_atualizados = 0
        docs_criados = 0
        docs_atualizados = 0
        docs_reatribuidos = 0
        grupos_criados = 0
        grupos_atualizados = 0
        permissoes_vinculadas = 0
        permissoes_ausentes = 0

        formas_existentes = list(FormasDePagamento.objects.all())
        for nome in FORMAS_PAGAMENTO_CANONICAS:
            forma = next(
                (f for f in formas_existentes if _normalizar_rotulo(f.forma_pagamento) == _normalizar_rotulo(nome)),
                None,
            )
            if forma is None:
                FormasDePagamento.objects.create(forma_pagamento=nome, ativo=True)
                formas_criadas += 1
                self.stdout.write(f"Forma criada: {nome}")
                continue

            mudou = False
            if forma.forma_pagamento != nome:
                forma.forma_pagamento = nome
                mudou = True
            if not forma.ativo:
                forma.ativo = True
                mudou = True
            if mudou:
                forma.save(update_fields=["forma_pagamento", "ativo"])
                formas_atualizadas += 1
                self.stdout.write(f"Forma atualizada: {nome}")

        tipos_existentes = list(TiposDePagamento.objects.all())
        for nome in TIPOS_PAGAMENTO_CANONICOS:
            tipo = next(
                (t for t in tipos_existentes if _normalizar_rotulo(t.tipo_de_pagamento) == _normalizar_rotulo(nome)),
                None,
            )
            if tipo is None:
                TiposDePagamento.objects.create(tipo_de_pagamento=nome, ativo=True)
                tipos_criados += 1
                self.stdout.write(f"Tipo de pagamento criado: {nome}")
                continue

            mudou = False
            if tipo.tipo_de_pagamento != nome:
                tipo.tipo_de_pagamento = nome
                mudou = True
            if not tipo.is_active:
                tipo.is_active = True
                mudou = True
            if mudou:
                tipo.save(update_fields=["tipo_de_pagamento", "is_active"])
                tipos_atualizados += 1
                self.stdout.write(f"Tipo de pagamento atualizado: {nome}")

        contas_fixas = TiposDePagamento.objects.get(tipo_de_pagamento="CONTAS FIXAS")
        docs_existentes = list(TiposDeDocumento.objects.select_related("tipo_de_pagamento"))
        for nome_doc in DOCUMENTOS_CONTAS_FIXAS_CANONICOS:
            doc_vinculado = next(
                (
                    d
                    for d in docs_existentes
                    if d.tipo_de_pagamento_id == contas_fixas.id
                    and _normalizar_rotulo(d.tipo_de_documento) == _normalizar_rotulo(nome_doc)
                ),
                None,
            )
            if doc_vinculado:
                mudou = False
                if doc_vinculado.tipo_de_documento != nome_doc:
                    doc_vinculado.tipo_de_documento = nome_doc
                    mudou = True
                if not doc_vinculado.is_active:
                    doc_vinculado.is_active = True
                    mudou = True
                if mudou:
                    doc_vinculado.save(update_fields=["tipo_de_documento", "is_active"])
                    docs_atualizados += 1
                    self.stdout.write(f"Documento atualizado (CONTAS FIXAS): {nome_doc}")
                continue

            doc_geral = next(
                (
                    d
                    for d in docs_existentes
                    if d.tipo_de_pagamento_id is None
                    and _normalizar_rotulo(d.tipo_de_documento) == _normalizar_rotulo(nome_doc)
                ),
                None,
            )
            if doc_geral:
                doc_geral.tipo_de_pagamento = contas_fixas
                doc_geral.tipo_de_documento = nome_doc
                doc_geral.is_active = True
                doc_geral.save(update_fields=["tipo_de_pagamento", "tipo_de_documento", "is_active"])
                docs_reatribuidos += 1
                self.stdout.write(f"Documento reatribuído para CONTAS FIXAS: {nome_doc}")
                continue

            TiposDeDocumento.objects.create(
                tipo_de_pagamento=contas_fixas,
                tipo_de_documento=nome_doc,
                is_active=True,
            )
            docs_criados += 1
            self.stdout.write(f"Documento criado (CONTAS FIXAS): {nome_doc}")

        content_type = ContentType.objects.get_for_model(Processo)
        for nome_grupo, codenames in GRUPOS_PERMISSOES.items():
            grupo, created = Group.objects.get_or_create(name=nome_grupo)
            if created:
                grupos_criados += 1
                self.stdout.write(f"Grupo criado: {nome_grupo}")
            else:
                grupos_atualizados += 1
                self.stdout.write(f"Grupo atualizado (reset de permissões): {nome_grupo}")

            grupo.permissions.clear()
            for codename in codenames:
                try:
                    permissao = Permission.objects.get(codename=codename, content_type=content_type)
                    grupo.permissions.add(permissao)
                    permissoes_vinculadas += 1
                except Permission.DoesNotExist:
                    permissoes_ausentes += 1
                    self.stdout.write(self.style.WARNING(f"Permissão ausente: {codename}"))

        self.stdout.write(
            self.style.SUCCESS(
                "Headstart concluído. "
                f"Formas (criadas={formas_criadas}, atualizadas={formas_atualizadas}) | "
                f"Tipos (criadas={tipos_criados}, atualizadas={tipos_atualizados}) | "
                f"Docs CONTAS FIXAS (criadas={docs_criados}, atualizadas={docs_atualizados}, reatribuidas={docs_reatribuidos}) | "
                f"Grupos (criados={grupos_criados}, atualizados={grupos_atualizados}, "
                f"permissoes_vinculadas={permissoes_vinculadas}, permissoes_ausentes={permissoes_ausentes})"
            )
        )
