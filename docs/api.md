# Referência de API

## Autenticação e Autorização

Todas as rotas da aplicação requerem autenticação (via `GlobalLoginRequiredMiddleware`). Requisições sem sessão válida recebem redirecionamento para `/accounts/login/`.

Além da autenticação, cada endpoint exige uma permissão específica declarada com `@permission_required('app_label.codename', raise_exception=True)`. Acesso não autorizado retorna **HTTP 403** — nunca redireciona para o login.

Consulte a [Matriz de Permissões](governanca/matriz_permissoes.md) para o mapeamento completo de codenames por perfil.

---

## Contrato de Erros Comuns

| Código | Significado | Como a UI trata |
|---|---|---|
| `400` | Entrada inválida (payload mal formado, parâmetro ausente) | Resposta JSON com `{"error": "mensagem"}` nos endpoints JSON; mensagem flash nos fluxos de formulário |
| `403` | Permissão negada (usuário autenticado mas sem codename) | HTTP 403 direto — sem redirect |
| `404` | Recurso não encontrado | HTTP 404 padrão do Django |

Fluxos de formulário HTML surfaceiam erros de negócio via sistema de mensagens Django (`messages.error` / `messages.warning`) renderizados pelo partial `layouts/_messages.html`.

---

## Restrições de Upload de Arquivo

- **Formatos aceitos:** PDF, JPEG, PNG (validados por magic bytes).
- **Tamanho máximo:** 20 MB (configurado no Nginx via `client_max_body_size`).
- **Storage:** volume Docker `media_volume`, servido em `/media/` pelo Nginx.

---

## Domínio Fiscal

**Permissão base:** `fiscal.acesso_backoffice`

### Endpoints de Formulário (HTML)

| Método | Path | Permissão | Descrição | Redirect sucesso |
|---|---|---|---|---|
| `POST` | `/impostos/agrupar/` | `fiscal.acesso_backoffice` | Agrupa `RetencaoImposto` selecionadas em um `Processo` de recolhimento | `editar_processo(pk)` |
| `POST` | `/impostos/anexar-documentos/` | `fiscal.acesso_backoffice` | Anexa guia, comprovante e relatório mensal a processos de recolhimento | `painel_impostos_view` |

### Endpoints JSON / File Response

| Método | Path | Permissão | Descrição | Resposta sucesso |
|---|---|---|---|---|
| `POST` | `/reinf/gerar-lotes/` | `fiscal.acesso_backoffice` | Gera XMLs de lotes EFD-Reinf para a competência informada | `200` + arquivo ZIP |
| `POST` | `/reinf/transmitir-lotes/` | `fiscal.acesso_backoffice` | Transmite lotes EFD-Reinf pendentes | `200` JSON |

**Parâmetros — `/reinf/gerar-lotes/`:**

| Campo | Tipo | Obrigatório | Formato |
|---|---|---|---|
| `competencia` | string | sim | `MM/AAAA` ou `AAAA-MM` |

**Erros — `/reinf/gerar-lotes/`:** `400` quando competência ausente ou inválida; `404` quando não há lotes elegíveis.

---

## Domínio Verbas Indenizatórias

**Permissões:** ver [Matriz de Permissões](governanca/matriz_permissoes.md) — seção Verbas Indenizatórias.

### Endpoints de Formulário (HTML)

| Método | Path | Permissão | Descrição | Redirect sucesso |
|---|---|---|---|---|
| `POST` | `/verbas/diarias/nova/action/` | `pagamentos.pode_criar_diarias` | Cria diária em status `RASCUNHO` | `gerenciar_diaria(pk)` |
| `POST` | `/verbas/diarias/<pk>/solicitar-autorizacao/` | `pagamentos.pode_gerenciar_diarias` | Avança diária para `SOLICITADA` | `gerenciar_diaria(pk)` |
| `POST` | `/verbas/diarias/<pk>/autorizar/` | `pagamentos.pode_autorizar_diarias` | Avança diária para `APROVADA` apenas quando o usuário é o proponente vinculado da diária | `gerenciar_diaria(pk)` |
| `POST` | `/verbas/agrupar/<tipo_verba>/` | `pagamentos.pode_agrupar_verbas` | Agrupa itens elegíveis em processo de pagamento | `editar_processo_verbas(pk)` |

---

## Domínio Suprimentos de Fundos

**Permissões:** `suprimentos.acesso_backoffice` (cadastro/cancelamento) + permissões granulares por etapa.

### Endpoints de Formulário (HTML)

| Método | Path | Permissão | Descrição | Redirect sucesso |
|---|---|---|---|---|
| `POST` | `/suprimentos/novo/action/` | `suprimentos.acesso_backoffice` | Cria `SuprimentoDeFundos` (status `ABERTO`) e `Processo` em `A EMPENHAR` | `gerenciar_suprimento_view(pk)` |
| `POST` | `/suprimentos/<pk>/despesas/adicionar/` | `suprimentos.pode_adicionar_despesas_suprimento` | Registra despesa e anexo de comprovante no suprimento | `gerenciar_suprimento_view(pk)` |
| `POST` | `/suprimentos/<pk>/fechar/` | `suprimentos.pode_encerrar_suprimento` | Encerra suprimento; Processo vai para `PAGO - EM CONFERÊNCIA` | `suprimentos_list` |
| `POST` | `/suprimentos/<pk>/prestacao/enviar/` | `suprimentos.pode_gerir_prestacao_contas_suprimento` | Suprido envia prestação para revisão (status `ENVIADA`) | `gerenciar_suprimento_view(pk)` |
| `POST` | `/suprimentos/prestacoes/<pk>/aprovar/` | `suprimentos.pode_gerir_prestacao_contas_suprimento` | Operador aprova prestação; gera devolução do saldo remanescente | `revisar_prestacoes_suprimento` |

---

## Domínio Pagamentos (Core)

**Permissões:** ver [Matriz de Permissões](governanca/matriz_permissoes.md) — seção Pagamentos.

> **Nota:** as permissões do fluxo principal usam o namespace `pagamentos.*`, conforme decorators e permissões declaradas no modelo financeiro principal.

### Endpoints de Formulário (HTML) — Seleção Principal

| Método | Path | Permissão | Descrição |
|---|---|---|---|
| `POST` | `/adicionar/action/` | `pagamentos.pode_editar_processos_pagamento` | Cria novo processo financeiro |
| `POST` | `/api/processo/<processo_pk>/salvar-nota-fiscal/<nota_pk>/` | `pagamentos.operador_contas_a_pagar` | Cria/edita nota fiscal e retenções do processo |
| `POST` | `/processo/<pk>/avancar-para-pagamento/` | `pagamentos.operador_contas_a_pagar` | Avança processo para próxima etapa (turnpike aplicado) |
| `POST` | `/processos/autorizar-pagamento/` | `pagamentos.pode_autorizar_pagamento` | Autoriza processos em lote |
| `POST` | `/liquidacoes/atestar/<pk>/` | `pagamentos.operador_contas_a_pagar` | Alterna ateste da nota fiscal |
| `POST` | `/processos/contabilizacao/<pk>/aprovar/` | `pagamentos.pode_contabilizar` | Registro contábil pós-pagamento |
| `POST` | `/processos/arquivamento/<pk>/executar/` | `pagamentos.pode_arquivar` | Arquivamento definitivo |
| `POST` | `/contingencias/nova/enviar/` | `pagamentos.operador_contas_a_pagar` | Abre contingência processual |
| `POST` | `/contingencias/<pk>/analisar/` | `pagamentos.operador_contas_a_pagar` | Aprova/recusa contingência conforme etapa |

### Endpoints JSON

| Método | Path | Permissão | Descrição | Resposta sucesso |
|---|---|---|---|---|
| `POST` | `/api/comprovantes/vincular/` | `pagamentos.operador_contas_a_pagar` | Vinculação de comprovantes de pagamento a processos | `200` JSON |

---

## Domínio Credores

**Permissão base:** `pagamentos.operador_contas_a_pagar`

### Endpoints de Formulário (HTML)

| Método | Path | Permissão | Descrição | Redirect sucesso |
|---|---|---|---|---|
| `POST` | `/adicionar-credor/action/` | `pagamentos.operador_contas_a_pagar` | Cadastra novo credor | `gerenciar_credor_view(pk)` |
| `POST` | `/credores/<pk>/editar/action/` | `pagamentos.operador_contas_a_pagar` | Atualiza dados cadastrais e bancários | `gerenciar_credor_view(pk)` |

---

## Referência Automática de Módulos

::: commons

::: credores

::: fiscal

::: pagamentos

::: suprimentos

::: verbas_indenizatorias
