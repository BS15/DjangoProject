# Changelog

Todas as mudanças notáveis neste projeto são documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

> **Nota — Clean Slate Protocol (Pré-V1):** Durante a fase pré-V1, mudanças de schema incompatíveis são resolvidas com reinicialização do banco de dados ao invés de migrações complexas de dados. Alterações de schema quebradas são registradas aqui com a indicação `[CLEAN SLATE]` ao invés de notas de migração.

---

## [Não Lançado]

_Mudanças em desenvolvimento ativo que ainda não foram versionadas._

---

## [0.1.0-alpha] — Pré-V1

Estado atual do sistema ao final da fase de bootstrapping.

### Adicionado

#### Domínio Pagamentos
- Esteira completa de processos financeiros: A EMPENHAR → AGUARDANDO LIQUIDAÇÃO → EM LIQUIDAÇÃO → AGUARDANDO PAGAMENTO → PAGO → PAGO - EM CONFERÊNCIA → CONTABILIZADO → ARQUIVADO.
- Cadastro e edição de processos com Nota Fiscal, retenções de impostos e documentos anexos.
- Devoluções processuais e Contingências com fluxo de aprovação hierárquica.
- Integração com SISCAC para conciliação de comprovantes bancários.
- Integração com API Autentique para assinatura digital de documentos.
- Painel de Contas a Pagar com empenho, autorização e lançamento bancário.
- Painel de Conferência e Contabilização pós-pagamento.

#### Domínio Verbas Indenizatórias
- Diárias: ciclo RASCUNHO → SOLICITADA → APROVADA, com agrupamento em processo de pagamento.
- Reembolsos, Auxílios e Jetons com fluxo de autorização e agrupamento.
- Revisão por operador de contas a pagar antes do agrupamento (status REVISADA obrigatório).

#### Domínio Suprimentos de Fundos
- Criação de suprimento com geração automática de Processo em A EMPENHAR.
- Registro de despesas pelo suprido.
- Prestação de Contas formal: ABERTA → ENVIADA → ENCERRADA.
- Devolução automática do saldo remanescente ao fechar a prestação.

#### Domínio Fiscal
- Painel de retenções de impostos com agrupamento em Processo IMPOSTOS.
- Anexação de guias e comprovantes por competência.
- Geração e transmissão de lotes EFD-Reinf.

#### Domínio Credores
- Cadastro e manutenção de credores com dados bancários.

#### Infraestrutura
- RBAC por domínio via `@permission_required` com `raise_exception=True`.
- `GlobalLoginRequiredMiddleware` protegendo todas as rotas.
- Validação de uploads por magic bytes (PDF, JPEG, PNG).
- Trilha de auditoria imutável via `django-simple-history`.
- Wiki MkDocs Material publicada com arquitetura, fluxos, RBAC e referência de API.
- Documentação de operações: deploy, backup/restore, monitoramento e troubleshooting.
