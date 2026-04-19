# Matriz de Permissões (RBAC)

O PaGé adota controle de acesso por permissões explícitas por domínio funcional.

## Diretriz técnica
- Proteção de endpoints com `@permission_required('app_label.permission_name', raise_exception=True)`.
- Sem uso de atalho por grupos customizados na camada de view.
- Sem dependência operacional do Django Admin para usuários finais.

## Objetivo de negócio
- Garantir segregação de funções.
- Evitar aprovações indevidas.
- Permitir rastreabilidade por perfil e por ação executada.

## Estrutura recomendada de matriz
- Ação operacional.
- Permissão requerida.
- Perfis autorizados.
- Risco mitigado.

## Matriz de Permissões por Domínio

### Domínio Fiscal

| Ação Operacional | Permissão Requerida | Perfil Autorizado | Risco Mitigado |
|---|---|---|---|
| Agrupamento de retenções, anexação documental e geração/transmissão EFD-Reinf | `fiscal.acesso_backoffice` | Operador Fiscal | Acesso não autorizado a dados tributários e geração de obrigação acessória; retorna 403 (não redireciona para login). |

### Domínio Fluxo

| Ação Operacional | Permissão Requerida | Perfil Autorizado | Risco Mitigado |
|---|---|---|---|
| Criação de diária | `fluxo.pode_criar_diarias` | Operador de Pagamentos | Inclusão de despesa indenizatória sem autorização de cadastro; retorna 403 (não redireciona para login). |
| Gestão operacional de diárias | `fluxo.pode_gerenciar_diarias` | Responsável por Liquidação/Conferência de Diárias | Alteração indevida de status e comprovantes de diária; retorna 403 (não redireciona para login). |
| Gestão operacional de reembolsos | `fluxo.pode_gerenciar_reembolsos` | Autorizador de Verbas | Pagamento de reembolso sem validação formal de competência; retorna 403 (não redireciona para login). |
| Gestão operacional de auxílios | `fluxo.pode_gerenciar_auxilios` | Autorizador de Verbas | Concessão de benefício indenizatório sem elegibilidade validada; retorna 403 (não redireciona para login). |

### Domínio Verbas Indenizatórias

| Ação Operacional | Permissão Requerida | Perfil Autorizado | Risco Mitigado |
|---|---|---|---|
| Agrupar verbas em processo de pagamento | `verbas_indenizatorias.pode_agrupar_verbas` | Operador de Verbas | Consolidação financeira indevida de itens sem governança; retorna 403 (não redireciona para login). |
| Gerir capa, documentos e pendências do processo de verbas | `verbas_indenizatorias.pode_gerenciar_processos_verbas` | Operador de Verbas | Edição indevida de dados processuais e documentais; retorna 403 (não redireciona para login). |
| Gerir ciclo de vida de jetons | `verbas_indenizatorias.pode_gerenciar_jetons` | Autorizador de Verbas | Autorização/cancelamento de jeton por perfil sem competência; retorna 403 (não redireciona para login). |

### Domínio Suprimentos

| Ação Operacional | Permissão Requerida | Perfil Autorizado | Risco Mitigado |
|---|---|---|---|
| Criação de suprimento, registro de despesas e fechamento da prestação | `suprimentos.acesso_backoffice` | Operador de Suprimentos | Concessão de adiantamento e baixa de prestação sem controle; retorna 403 (não redireciona para login). |

### Domínio Credores

| Ação Operacional | Permissão Requerida | Perfil Autorizado | Risco Mitigado |
|---|---|---|---|
| Cadastro, atualização e gestão cadastral de credores | `pagamentos.acesso_backoffice` | Operador de Cadastro Financeiro | Alteração indevida de favorecidos e dados bancários; retorna 403 (não redireciona para login). |
