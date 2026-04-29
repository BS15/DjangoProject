# Catálogo de Permissões e Grupos

Esta página concentra o inventário operacional atual de controle de acesso do PaGé: como as permissões são aplicadas, quais permissões estão disponíveis e quais grupos canônicos já são provisionados pelo projeto.

## Como o RBAC funciona no PaGé

- O controle de acesso é feito por permissão explícita nos endpoints, com `@permission_required("app_label.codename", raise_exception=True)`.
- O nome do grupo não libera acesso por si só. O que efetivamente autoriza uma operação é a permissão vinculada ao usuário, normalmente herdada via grupo.
- Os grupos são perfis operacionais prontos para provisionamento inicial e para ambientes de demonstração ou desenvolvimento.
- O painel de desenvolvedor de permissões expõe uma visão consolidada de usuários, grupos e permissões para auditoria operacional.

## Fontes canônicas atuais

As permissões abaixo vêm de três fontes do código:

- Permissões declaradas no modelo financeiro principal (`pagamentos/domain_models/processos.py`), que concentra tanto permissões do fluxo de pagamentos quanto de verbas indenizatórias.
- Permissões declaradas nos modelos próprios de verbas (`verbas_indenizatorias/models.py`) e suprimentos (`suprimentos/models.py`).
- Grupos canônicos provisionados pelo comando `setup_headstart` (`pagamentos/management/commands/setup_headstart.py`).

## Permissões disponíveis

## Pagamentos Core e Credores

Estas permissões estão declaradas em `pagamentos/domain_models/processos.py` e são usadas nas views de cadastro, empenho, liquidação, pagamento, conferência, contabilização, arquivamento, contingência, credores e ferramentas auxiliares.

| Codename | Escopo em runtime | Finalidade operacional |
|---|---|---|
| `pagamentos.operador_contas_a_pagar` | Credores, contingência, documentos, sync e apoio operacional | Permissão-base do backoffice financeiro; usada principalmente no módulo de credores e APIs auxiliares. |
| `pagamentos.pode_visualizar_processos_pagamento` | Painel principal e detalhe de processo | Visualização de processos de pagamento sem acesso de mutação. |
| `pagamentos.pode_editar_processos_pagamento` | Cadastro/edição de capa, documentos, pendências e fiscal | Gestão de edição de processos de pagamento. |
| `pagamentos.pode_aprovar_contingencia_supervisor` | Contingências em etapa de supervisão/gerência | Aprovação de contingências pelo perfil supervisor. |
| `pagamentos.pode_aprovar_contingencia_ordenador` | Contingências em etapa do Ordenador de Despesa | Aprovação de contingências que exigem anuência do ordenador. |
| `pagamentos.pode_aprovar_contingencia_conselho` | Contingências em etapa do Conselho Fiscal | Aprovação de contingências que exigem deliberação do conselho. |
| `pagamentos.pode_revisar_contingencia_contadora` | Contingências em etapa de revisão contábil | Revisão contábil final de contingências aprovadas pela cadeia hierárquica. |
| `pagamentos.pode_atestar_liquidacao` | Liquidação | Permissão dedicada existente no domínio; o fluxo atual de ateste usa guarda contextual por `liquidacao.fiscal_contrato` com fallback de backoffice (`pagamentos.operador_contas_a_pagar`). |
| `pagamentos.pode_autorizar_pagamento` | Autorização | Aprovação ou recusa formal de pagamento. |
| `pagamentos.pode_contabilizar` | Pós-pagamento | Registro e recusa contábil. |
| `pagamentos.pode_auditar_conselho` | Conselho fiscal e reuniões | Deliberação final e acesso ampliado de auditoria. |
| `pagamentos.pode_arquivar` | Pós-pagamento | Arquivamento definitivo do processo. |

## Verbas indenizatórias — escopo pagamentos

Estas permissões estão declaradas junto ao modelo financeiro principal em `pagamentos/domain_models/processos.py` e são consumidas em runtime com o prefixo `pagamentos.` nas views e templates de verbas.

| Codename | Escopo em runtime | Finalidade operacional |
|---|---|---|
| `pagamentos.pode_visualizar_verbas` | Painéis e listagens | Acesso de consulta ao módulo de verbas. |
| `verbas_indenizatorias.pode_criar_diarias` | Diárias | Cadastro inicial de solicitações de diárias. |
| `pagamentos.pode_importar_diarias` | Diárias | Importação em lote. |
| `verbas_indenizatorias.pode_gerenciar_diarias` | Diárias | Edição, documentos, assinaturas e PDFs. |
| `pagamentos.pode_autorizar_diarias` | Diárias | Aprovação de diárias pendentes, restrita às diárias em que o usuário é o proponente vinculado. |
| `pagamentos.pode_gerenciar_reembolsos` | Reembolsos | Cadastro e gestão operacional de reembolsos. |
| `pagamentos.pode_gerenciar_jetons` | Jetons | Cadastro e gestão operacional de jetons. |
| `pagamentos.pode_gerenciar_auxilios` | Auxílios | Cadastro e gestão operacional de auxílios. |
| `verbas_indenizatorias.pode_agrupar_verbas` | Processo de verbas | Agrupamento de itens aprovados em processo de pagamento. |
| `verbas_indenizatorias.pode_gerenciar_processos_verbas` | Processo de verbas | Gestão da capa, documentos e pendências processuais de verbas. |
| `pagamentos.pode_sincronizar_diarias_siscac` | Diárias | Sincronização/importação via SISCAC. |

## Verbas indenizatórias — escopo próprio

Estas permissões estão declaradas em `verbas_indenizatorias/models.py` e são consumidas diretamente com o prefixo `verbas_indenizatorias.` nas views de prestação de contas de diárias.

| Codename | Escopo em runtime | Finalidade operacional |
|---|---|---|
| `verbas_indenizatorias.operar_prestacao_contas` | Prestação de contas de diárias | Operação de prestação de contas em nome de terceiros (beneficiário). |
| `verbas_indenizatorias.visualizar_prestacao_contas` | Painel de revisão de prestações | Acesso de leitura ao painel consolidado de prestações de contas de diárias. |
| `verbas_indenizatorias.analisar_prestacao_contas` | Revisão e aceite de prestações | Revisão, análise e aceite formal de prestações de contas de diárias. |

## Suprimentos

| Codename | Escopo em runtime | Finalidade operacional |
|---|---|---|
| `suprimentos.acesso_backoffice` | Listagem e cadastro inicial de suprimentos | Acesso operacional ao backoffice de suprimentos. |
| `suprimentos.pode_gerenciar_concessao_suprimento` | Concessão e cancelamento de suprimento | Abertura de novo suprimento de fundos e spoke de cancelamento. |
| `suprimentos.pode_adicionar_despesas_suprimento` | Despesas de suprimento | Registro manual de despesas e anexos de comprovantes no suprimento. |
| `suprimentos.pode_encerrar_suprimento` | Encerramento do suprimento | Encerramento da prestação do suprimento e avanço para conferência. |
| `suprimentos.pode_gerir_prestacao_contas_suprimento` | Prestação de contas de suprimento | Envio, revisão, aprovação e emissão de relatório PDF da prestação de contas de suprimento. |

## Fiscal

| Codename | Escopo em runtime | Finalidade operacional |
|---|---|---|
| `fiscal.acesso_backoffice` | Impostos e EFD-Reinf | Acesso operacional ao backoffice fiscal. |

Observação: `fiscal.acesso_backoffice` está presente nas views do módulo fiscal. Por se tratar de permissão customizada, ela deve ser provisionada explicitamente no banco (via `Meta.permissions` em modelo/migração ou rotina de bootstrap), não apenas pelo uso em decorator.

## Grupos canônicos de usuários

Os grupos abaixo estão definidos no `setup_headstart` e representam os perfis operacionais provisionados automaticamente. A coluna de permissões reflete exatamente o código do comando.

| Grupo | Permissões vinculadas |
|---|---|
| `FUNCIONARIO(A) CONTAS A PAGAR` | `pagamentos.pode_visualizar_processos_pagamento`, `pagamentos.operador_contas_a_pagar`, `pagamentos.pode_arquivar`, `suprimentos.pode_gerenciar_concessao_suprimento`, `suprimentos.pode_gerir_prestacao_contas_suprimento`, `verbas_indenizatorias.analisar_prestacao_contas`, `pagamentos.pode_visualizar_verbas`, `verbas_indenizatorias.visualizar_prestacao_contas` |
| `SUPERVISOR(A) CONTAS A PAGAR` | `pagamentos.pode_visualizar_processos_pagamento`, `pagamentos.operador_contas_a_pagar`, `pagamentos.pode_aprovar_contingencia_supervisor`, `pagamentos.pode_arquivar`, `suprimentos.pode_gerenciar_concessao_suprimento`, `suprimentos.pode_gerir_prestacao_contas_suprimento`, `verbas_indenizatorias.analisar_prestacao_contas`, `pagamentos.pode_visualizar_verbas`, `verbas_indenizatorias.visualizar_prestacao_contas` |
| `ORDENADOR(A) DE DESPESA` | `pagamentos.pode_visualizar_processos_pagamento`, `pagamentos.pode_autorizar_pagamento`, `pagamentos.pode_aprovar_contingencia_ordenador` |
| `CONTADOR(A)` | `pagamentos.pode_visualizar_processos_pagamento`, `pagamentos.pode_contabilizar`, `pagamentos.pode_revisar_contingencia_contadora` |
| `CONSELHEIRO(A) FISCAL` | `pagamentos.pode_visualizar_processos_pagamento`, `pagamentos.pode_auditar_conselho`, `pagamentos.pode_aprovar_contingencia_conselho` |

## Grupos usados em usuários de teste RBAC

O gerador de usuários hipotéticos de teste cobre todos os grupos canônicos:

- `FUNCIONARIO(A) CONTAS A PAGAR`
- `SUPERVISOR(A) CONTAS A PAGAR`
- `ORDENADOR(A) DE DESPESA`
- `CONTADOR(A)`
- `CONSELHEIRO(A) FISCAL`

Esses perfis são usados para acelerar homologação, depuração e validação manual das telas protegidas por permissão.

## Leitura recomendada deste catálogo

- Use esta página para descobrir se uma permissão já existe e quais grupos a recebem por padrão.
- Use a [Matriz de Permissões](matriz_permissoes.md) quando a pergunta for de segregação de funções, risco mitigado e responsabilidade por etapa do processo.
- Use o painel RBAC de desenvolvedor quando for necessário auditar a composição real de usuários, grupos e permissões no banco atual.