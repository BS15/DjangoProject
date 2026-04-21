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

### Domínio Verbas Indenizatórias

| Ação Operacional | Permissão Requerida | Perfil Autorizado | Risco Mitigado |
|---|---|---|---|
| Criação de diária | `verbas_indenizatorias.pode_criar_diarias` | Operador de Pagamentos | Inclusão de despesa indenizatória sem autorização de cadastro; retorna 403 (não redireciona para login). |
| Gestão operacional de diárias | `verbas_indenizatorias.pode_gerenciar_diarias` | Responsável por Liquidação/Conferência de Diárias | Alteração indevida de status e comprovantes de diária; retorna 403 (não redireciona para login). |
| Gestão operacional de reembolsos | `verbas_indenizatorias.pode_gerenciar_reembolsos` | Autorizador de Verbas | Pagamento de reembolso sem validação formal de competência; retorna 403 (não redireciona para login). |
| Gestão operacional de auxílios | `verbas_indenizatorias.pode_gerenciar_auxilios` | Autorizador de Verbas | Concessão de benefício indenizatório sem elegibilidade validada; retorna 403 (não redireciona para login). |
| Agrupar verbas em processo de pagamento | `verbas_indenizatorias.pode_agrupar_verbas` | Operador de Verbas | Consolidação financeira indevida de itens sem governança; retorna 403 (não redireciona para login). |
| Gerir capa, documentos e pendências do processo de verbas | `verbas_indenizatorias.pode_gerenciar_processos_verbas` | Operador de Verbas | Edição indevida de dados processuais e documentais; retorna 403 (não redireciona para login). |
| Gerir ciclo de vida de jetons | `verbas_indenizatorias.pode_gerenciar_jetons` | Autorizador de Verbas | Autorização/cancelamento de jeton por perfil sem competência; retorna 403 (não redireciona para login). |

### Domínio Suprimentos

| Ação Operacional | Permissão Requerida | Perfil Autorizado | Risco Mitigado |
|---|---|---|---|
| Criação de suprimento, registro de despesas e fechamento da prestação | `suprimentos.acesso_backoffice` | Operador de Suprimentos | Concessão de adiantamento e baixa de prestação sem controle; retorna 403 (não redireciona para login). |

### Domínio Pagamentos

Observação técnica: o workflow financeiro principal usa codenames `fluxo.*` porque as permissões canônicas do processo estão declaradas no modelo de domínio financeiro com `app_label` `fluxo`, embora o código-fonte resida no pacote `pagamentos/`. O subdomínio de credores continua usando `pagamentos.acesso_backoffice`.

| Ação Operacional | Permissão Requerida | Perfil Autorizado | Risco Mitigado |
|---|---|---|---|
| Cadastro e edição geral de processos, documentos, pendências, devoluções e abertura de contingências | `fluxo.acesso_backoffice` | Operador Financeiro Backoffice | Alteração indevida de dados processuais, anexos e exceções do fluxo sem competência operacional; retorna 403 (não redireciona para login). |
| Empenho, avanço para pagamento, contas a pagar, lançamento bancário, conferência, sync SISCAC e APIs operacionais de comprovantes | `fluxo.pode_operar_contas_pagar` | Funcionário(a) Contas a Pagar | Movimentação indevida do processo entre etapas críticas de pagamento, conciliação externa ou tratamento de comprovantes sem segregação de função; retorna 403 (não redireciona para login). |
| Ateste de notas fiscais na etapa de liquidação | `fluxo.pode_atestar_liquidacao` | Fiscal de Contrato | Liquidação documental sem validação do fiscal responsável, com risco de pagamento indevido; retorna 403 (não redireciona para login). |
| Autorização e recusa de pagamentos | `fluxo.pode_autorizar_pagamento` | Ordenador(a) de Despesa | Liberação ou bloqueio indevido de despesa sem autoridade formal de ordenação; retorna 403 (não redireciona para login). |
| Aprovação de contingências na etapa de supervisão/gerência | `fluxo.pode_aprovar_contingencia_supervisor` | Supervisor/Gerência de Contas a Pagar | Aprovação excepcional de alteração processual sem revisão hierárquica adequada; retorna 403 (não redireciona para login). |
| Contabilização e recusa contábil de processos pagos | `fluxo.pode_contabilizar` | Contador(a) | Registro contábil indevido ou devolução incorreta à conferência sem competência técnica; retorna 403 (não redireciona para login). |
| Deliberação do Conselho Fiscal, gestão de reuniões e painel consolidado de auditoria | `fluxo.pode_auditar_conselho` | Conselheiro(a) Fiscal | Aprovação final, recusa em conselho ou acesso ampliado à trilha de auditoria sem competência institucional; retorna 403 (não redireciona para login). |
| Arquivamento definitivo do processo | `fluxo.pode_arquivar` | Operador de Arquivamento Financeiro | Encerramento e consolidação definitiva do processo sem verificação formal de completude documental; retorna 403 (não redireciona para login). |

Observação de revisão: o endpoint auxiliar de upload em [pagamentos/views/pre_payment/cadastro/apis.py](https://github.com/BS15/DjangoProject/blob/main/pagamentos/views/pre_payment/cadastro/apis.py) foi alinhado para `fluxo.pode_operar_contas_pagar`, eliminando a referência ao codename não canônico `fluxo.pode_editar_processos`.

### Domínio Credores

| Ação Operacional | Permissão Requerida | Perfil Autorizado | Risco Mitigado |
|---|---|---|---|
| Cadastro, atualização e gestão cadastral de credores | `pagamentos.acesso_backoffice` | Operador Financeiro Backoffice | Alteração indevida de favorecidos e dados bancários; retorna 403 (não redireciona para login). |
