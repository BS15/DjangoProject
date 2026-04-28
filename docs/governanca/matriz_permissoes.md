# Matriz de Permissões (RBAC)

O PaGé adota controle de acesso por permissões explícitas por domínio funcional.

Consulte também o [Catálogo de Permissões e Grupos](catalogo_permissoes_grupos.md) para o inventário atual de permissões disponíveis, grupos canônicos e observações de implementação.

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
| Agrupamento de retenções, anexação documental e geração/transmissão EFD-Reinf | `fiscal.acesso_backoffice` | Operador Fiscal | Acesso não autorizado a dados tributários e geração de obrigação acessória. |

### Domínio Verbas Indenizatórias

| Ação Operacional | Permissão Requerida | Perfil Autorizado | Risco Mitigado |
|---|---|---|---|
| Criação de diária | `pagamentos.pode_criar_diarias` | Operador de Pagamentos | Inclusão de despesa indenizatória sem autorização de cadastro. |
| Gestão operacional de diárias | `pagamentos.pode_gerenciar_diarias` | Responsável por Liquidação/Conferência de Diárias | Alteração indevida de status e comprovantes de diária. |
| Gestão operacional de reembolsos | `pagamentos.pode_gerenciar_reembolsos` | Autorizador de Verbas | Pagamento de reembolso sem validação formal de competência. |
| Gestão operacional de auxílios | `pagamentos.pode_gerenciar_auxilios` | Autorizador de Verbas | Concessão de benefício indenizatório sem elegibilidade validada. |
| Agrupar verbas em processo de pagamento | `pagamentos.pode_agrupar_verbas` | Operador de Verbas | Consolidação financeira indevida de itens sem governança. |
| Gerir capa, documentos e pendências do processo de verbas | `pagamentos.pode_gerenciar_processos_verbas` | Operador de Verbas | Edição indevida de dados processuais e documentais. |
| Gerir ciclo de vida de jetons | `pagamentos.pode_gerenciar_jetons` | Autorizador de Verbas | Autorização/cancelamento de jeton por perfil sem competência. |

### Domínio Suprimentos

| Ação Operacional | Permissão Requerida | Perfil Autorizado | Risco Mitigado |
|---|---|---|---|
| Criação e cancelamento de suprimento | `suprimentos.acesso_backoffice` | Operador de Suprimentos | Concessão/cancelamento de adiantamento sem competência operacional. |
| Registro de despesas no suprimento | `suprimentos.pode_adicionar_despesas_suprimento` | Operador de Suprimentos - Despesas | Inclusão indevida de gastos e comprovantes em prestação. |
| Encerramento do suprimento | `suprimentos.pode_encerrar_suprimento` | Operador de Suprimentos - Encerramento | Fechamento indevido de ciclo com impacto no status do processo. |
| Envio, revisão e aprovação de prestação de contas | `suprimentos.pode_gerir_prestacao_contas_suprimento` | Gestor de Prestação de Contas de Suprimento | Aprovação indevida de prestação e devolução automática sem segregação. |

### Domínio Pagamentos

Observação técnica: o workflow financeiro principal usa codenames `pagamentos.*` declarados no modelo de domínio financeiro em `pagamentos/domain_models/processos.py`. O subdomínio de credores também usa `pagamentos.operador_contas_a_pagar`.

| Ação Operacional | Permissão Requerida | Perfil Autorizado | Risco Mitigado |
|---|---|---|---|
| Cadastro e edição geral de processos, documentos, pendências, devoluções e abertura de contingências | `pagamentos.pode_editar_processos_pagamento` | Operador Financeiro Backoffice | Alteração indevida de dados processuais, anexos e exceções do fluxo sem competência operacional. |
| Empenho, avanço para pagamento, contas a pagar, lançamento bancário, conferência, sync SISCAC e APIs operacionais de comprovantes | `pagamentos.operador_contas_a_pagar` | Funcionário(a) Contas a Pagar | Movimentação indevida do processo entre etapas críticas de pagamento, conciliação externa ou tratamento de comprovantes sem segregação de função. |
| Ateste de notas fiscais na etapa de liquidação | `pagamentos.pode_atestar_liquidacao` | Fiscal de Contrato | Liquidação documental sem validação do fiscal responsável, com risco de pagamento indevido. |
| Autorização e recusa de pagamentos | `pagamentos.pode_autorizar_pagamento` | Ordenador(a) de Despesa | Liberação ou bloqueio indevido de despesa sem autoridade formal de ordenação. |
| Aprovação de contingências na etapa de supervisão/gerência | `pagamentos.pode_aprovar_contingencia_supervisor` | Supervisor/Gerência de Contas a Pagar | Aprovação excepcional de alteração processual sem revisão hierárquica adequada. |
| Contabilização e recusa contábil de processos pagos | `pagamentos.pode_contabilizar` | Contador(a) | Registro contábil indevido ou devolução incorreta à conferência sem competência técnica. |
| Deliberação do Conselho Fiscal, gestão de reuniões e painel consolidado de auditoria | `pagamentos.pode_auditar_conselho` | Conselheiro(a) Fiscal | Aprovação final, recusa em conselho ou acesso ampliado à trilha de auditoria sem competência institucional. |
| Arquivamento definitivo do processo | `pagamentos.pode_arquivar` | Operador de Arquivamento Financeiro | Encerramento e consolidação definitiva do processo sem verificação formal de completude documental. |

### Domínio Credores

| Ação Operacional | Permissão Requerida | Perfil Autorizado | Risco Mitigado |
|---|---|---|---|
| Cadastro, atualização e gestão cadastral de credores | `pagamentos.operador_contas_a_pagar` | Operador contas a pagar | Alteração indevida de favorecidos e dados bancários. |
