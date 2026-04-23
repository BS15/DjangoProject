# Catálogo de Permissões e Grupos

Esta página concentra o inventário operacional atual de controle de acesso do PaGé: como as permissões são aplicadas, quais permissões estão disponíveis e quais grupos canônicos já são provisionados pelo projeto.

## Como o RBAC funciona no PaGé

- O controle de acesso é feito por permissão explícita nos endpoints, com `@permission_required("app_label.codename", raise_exception=True)`.
- O nome do grupo não libera acesso por si só. O que efetivamente autoriza uma operação é a permissão vinculada ao usuário, normalmente herdada via grupo.
- Os grupos são perfis operacionais prontos para provisionamento inicial e para ambientes de demonstração ou desenvolvimento.
- O painel de desenvolvedor de permissões expõe uma visão consolidada de usuários, grupos e permissões para auditoria operacional.

## Fontes canônicas atuais

As permissões abaixo vêm de três fontes do código:

- Permissões declaradas no modelo financeiro principal, que hoje concentra tanto permissões do fluxo de pagamentos quanto de verbas indenizatórias.
- Permissões declaradas nos modelos próprios de suprimentos.
- Grupos canônicos provisionados pelo comando `setup_headstart` e pelo utilitário de usuários de teste RBAC.

## Permissões disponíveis

## Pagamentos Core e Credores

Estas permissões estão declaradas no domínio financeiro principal e são usadas amplamente nas views de cadastro, liquidação, pagamento, conferência, contabilização, arquivamento, contingência, credores e ferramentas auxiliares.

| Codename | Escopo em runtime | Finalidade operacional |
|---|---|---|
| `pagamentos.operador_contas_a_pagar` | Pagamentos, credores, contingência, documentos, sync e apoio operacional | Permissão-base do backoffice financeiro. |
| `pagamentos.pode_visualizar_processos_pagamento` | Painel principal e detalhe de processo | Visualização de processos de pagamento sem acesso de mutação. |
| `pagamentos.pode_editar_processos_pagamento` | Cadastro/edição de capa, documentos, pendências e fiscal | Gestão de edição de processos de pagamento. |
| `pagamentos.pode_aprovar_contingencia_supervisor` | Contingências em etapa de supervisão/gerência | Aprovação excepcional de contingências. |
| `pagamentos.pode_atestar_liquidacao` | Liquidação | Ateste fiscal de notas e liquidação documental. |
| `pagamentos.pode_autorizar_pagamento` | Autorização | Aprovação ou recusa formal de pagamento. |
| `pagamentos.pode_contabilizar` | Pós-pagamento | Registro e recusa contábil. |
| `pagamentos.pode_auditar_conselho` | Conselho fiscal e reuniões | Deliberação final e acesso ampliado de auditoria. |
| `pagamentos.pode_arquivar` | Pós-pagamento | Arquivamento definitivo do processo. |

## Verbas indenizatórias

Embora pertençam ao domínio de verbas, essas permissões também estão declaradas no modelo financeiro principal e hoje são consumidas em runtime com o prefixo `pagamentos.` nas views e nos templates.

| Codename | Escopo em runtime | Finalidade operacional |
|---|---|---|
| `pagamentos.pode_visualizar_verbas` | Painéis e listagens | Acesso de consulta ao módulo de verbas. |
| `pagamentos.pode_criar_diarias` | Diárias | Cadastro inicial de solicitações de diárias. |
| `pagamentos.pode_importar_diarias` | Diárias | Importação em lote. |
| `pagamentos.pode_gerenciar_diarias` | Diárias | Edição, documentos, assinaturas e PDFs. |
| `pagamentos.pode_autorizar_diarias` | Diárias | Aprovação de diárias pendentes, restrita às diárias em que o usuário é o proponente vinculado. |
| `pagamentos.pode_gerenciar_reembolsos` | Reembolsos | Cadastro e gestão operacional de reembolsos. |
| `pagamentos.pode_gerenciar_jetons` | Jetons | Cadastro e gestão operacional de jetons. |
| `pagamentos.pode_gerenciar_auxilios` | Auxílios | Cadastro e gestão operacional de auxílios. |
| `pagamentos.pode_agrupar_verbas` | Processo de verbas | Agrupamento de itens em processo de pagamento. |
| `pagamentos.pode_gerenciar_processos_verbas` | Processo de verbas | Gestão da capa, documentos e pendências processuais. |
| `pagamentos.pode_sincronizar_diarias_siscac` | Diárias | Sincronização/importação via SISCAC. |

Observação: o modelo de verbas também declara permissões com os mesmos codenames em `verbas_indenizatorias/models.py`. Na prática, o código operacional atual consome os codenames pelo escopo `pagamentos.*`, então esta página documenta o comportamento efetivamente usado pelas views.

## Suprimentos

| Codename | Escopo em runtime | Finalidade operacional |
|---|---|---|
| `suprimentos.acesso_backoffice` | Cadastro, prestação de contas e PDFs de suprimentos | Acesso operacional ao backoffice de suprimentos. |
| `suprimentos.pode_adicionar_despesas_suprimento` | Despesas de suprimento | Registro manual de despesas e anexos de comprovantes no suprimento. |
| `suprimentos.pode_encerrar_suprimento` | Encerramento do suprimento | Encerramento da prestação do suprimento e avanço para conferência. |
| `suprimentos.pode_gerir_prestacao_contas_suprimento` | Prestação de contas de suprimento | Envio, revisão, aprovação e emissão de relatório PDF da prestação de contas de suprimento. |

## Fiscal

| Codename | Escopo em runtime | Finalidade operacional |
|---|---|---|
| `fiscal.acesso_backoffice` | Impostos e EFD-Reinf | Acesso operacional ao backoffice fiscal. |

Observação: o uso de `fiscal.acesso_backoffice` está presente nas views do módulo fiscal. Diferentemente de pagamentos, verbas e suprimentos, essa permissão não está hoje declarada em um bloco `Meta.permissions` localizado em `fiscal/models.py`, então o catálogo do módulo fiscal ainda depende do uso observado nas views.

## Grupos canônicos de usuários

Os grupos abaixo estão definidos no provisionamento inicial do projeto e representam os perfis operacionais hoje previstos.

| Grupo | Permissões vinculadas |
|---|---|
| `FUNCIONARIO(A) CONTAS A PAGAR` | `pagamentos.operador_contas_a_pagar`, `pagamentos.pode_visualizar_processos_pagamento`, `pagamentos.pode_editar_processos_pagamento`, `pagamentos.pode_aprovar_contingencia_supervisor`, `pagamentos.pode_arquivar`, `suprimentos.acesso_backoffice`, `suprimentos.pode_gerir_prestacao_contas_suprimento`, `verbas_indenizatorias.analisar_prestacao_contas` |
| `FISCAL DE CONTRATO` | `pagamentos.pode_atestar_liquidacao` |
| `ORDENADOR(A) DE DESPESA` | `pagamentos.pode_visualizar_processos_pagamento`, `pagamentos.pode_autorizar_pagamento` |
| `CONTADOR(A)` | `pagamentos.pode_visualizar_processos_pagamento`, `pagamentos.pode_contabilizar` |
| `CONSELHEIRO(A) FISCAL` | `pagamentos.pode_visualizar_processos_pagamento`, `pagamentos.pode_auditar_conselho` |
| `AUTORIZADOR(A) DE DIARIAS - PROPONENTE` | `pagamentos.pode_autorizar_diarias` |
| `OPERADOR(A) DE SUPRIMENTOS - DESPESAS` | `suprimentos.pode_adicionar_despesas_suprimento` |
| `OPERADOR(A) DE SUPRIMENTOS - ENCERRAMENTO` | `suprimentos.pode_encerrar_suprimento` |
| `GESTOR(A) DE PRESTACAO DE CONTAS DE SUPRIMENTO` | `suprimentos.pode_gerir_prestacao_contas_suprimento` |

## Grupos usados em usuários de teste RBAC

O gerador de usuários hipotéticos de teste cobre hoje um subconjunto dos grupos canônicos, voltado aos perfis principais do fluxo financeiro:

- `FUNCIONARIO(A) CONTAS A PAGAR`
- `FISCAL DE CONTRATO`
- `CONSELHEIRO(A) FISCAL`
- `CONTADOR(A)`
- `ORDENADOR(A) DE DESPESA`

Esses perfis são usados para acelerar homologação, depuração e validação manual das telas protegidas por permissão.

## Leitura recomendada deste catálogo

- Use esta página para descobrir se uma permissão já existe e quais grupos a recebem por padrão.
- Use a [Matriz de Permissões](matriz_permissoes.md) quando a pergunta for de segregação de funções, risco mitigado e responsabilidade por etapa do processo.
- Use o painel RBAC de desenvolvedor quando for necessário auditar a composição real de usuários, grupos e permissões no banco atual.