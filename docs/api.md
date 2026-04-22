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
| `POST` | `/verbas/diarias/criar/` | `verbas_indenizatorias.pode_criar_diarias` | Cria diária em status `RASCUNHO` | `gerenciar_diaria(pk)` |
| `POST` | `/verbas/diarias/<pk>/solicitar/` | `verbas_indenizatorias.pode_gerenciar_diarias` | Avança diária para `SOLICITADA` | `gerenciar_diaria(pk)` |
| `POST` | `/verbas/diarias/<pk>/autorizar/` | `verbas_indenizatorias.pode_gerenciar_diarias` | Avança diária para `APROVADA` | `gerenciar_diaria(pk)` |
| `POST` | `/verbas/agrupar/` | `verbas_indenizatorias.pode_agrupar_verbas` | Agrupa itens `REVISADA` em processo de pagamento | `detalhe_processo_verbas(pk)` |

---

## Domínio Suprimentos de Fundos

**Permissão base:** `suprimentos.acesso_backoffice`

### Endpoints de Formulário (HTML)

| Método | Path | Permissão | Descrição | Redirect sucesso |
|---|---|---|---|---|
| `POST` | `/suprimentos/criar/` | `suprimentos.acesso_backoffice` | Cria `SuprimentoDeFundos` (status `ABERTO`) e `Processo` em `A EMPENHAR` | `detalhe_suprimento(pk)` |
| `POST` | `/suprimentos/<pk>/fechar/` | `suprimentos.acesso_backoffice` | Encerra suprimento; Processo vai para `PAGO - EM CONFERÊNCIA` | `detalhe_suprimento(pk)` |
| `POST` | `/suprimentos/<pk>/prestacao/enviar/` | `suprimentos.acesso_backoffice` | Suprido envia prestação para revisão (status `ENVIADA`) | `detalhe_prestacao(pk)` |
| `POST` | `/suprimentos/<pk>/prestacao/aprovar/` | `suprimentos.acesso_backoffice` | Operador aprova prestação; gera devolução do saldo remanescente | `detalhe_prestacao(pk)` |

---

## Domínio Pagamentos (Core)

**Permissões:** ver [Matriz de Permissões](governanca/matriz_permissoes.md) — seção Pagamentos.

> **Nota:** as permissões do fluxo principal usam o `app_label` `fluxo` (não `pagamentos`), pois as permissões canônicas estão declaradas no modelo de domínio financeiro com esse label.

### Endpoints de Formulário (HTML) — Seleção Principal

| Método | Path | Permissão | Descrição |
|---|---|---|---|
| `POST` | `/processos/criar/` | `fluxo.acesso_backoffice` | Cria novo processo financeiro |
| `POST` | `/processos/<pk>/nota-fiscal/salvar/` | `fluxo.acesso_backoffice` | Cria/edita nota fiscal e retenções do processo |
| `POST` | `/processos/<pk>/avancar/` | `fluxo.pode_operar_contas_pagar` | Avança processo para próxima etapa (turnpike aplicado) |
| `POST` | `/processos/<pk>/autorizar/` | `fluxo.pode_autorizar_pagamento` | Ordena autorização ou recusa de pagamento |
| `POST` | `/processos/<pk>/atestar/` | `fluxo.pode_atestar_liquidacao` | Fiscal de contrato atesta nota fiscal |
| `POST` | `/processos/<pk>/contabilizar/` | `fluxo.pode_contabilizar` | Registro contábil pós-pagamento |
| `POST` | `/processos/<pk>/arquivar/` | `fluxo.pode_arquivar` | Arquivamento definitivo |
| `POST` | `/processos/<pk>/contingencia/` | `fluxo.acesso_backoffice` | Abre contingência processual |
| `POST` | `/processos/<pk>/contingencia/<cid>/aprovar/` | `fluxo.pode_aprovar_contingencia_supervisor` | Supervisor aprova contingência |

### Endpoints JSON

| Método | Path | Permissão | Descrição | Resposta sucesso |
|---|---|---|---|---|
| `POST` | `/processos/api/upload-documento/` | `fluxo.pode_operar_contas_pagar` | Upload avulso de documento (PDF/JPEG/PNG) | `200` JSON `{"id": <int>, "url": "<str>"}` |

---

## Domínio Credores

**Permissão base:** `pagamentos.acesso_backoffice`

### Endpoints de Formulário (HTML)

| Método | Path | Permissão | Descrição | Redirect sucesso |
|---|---|---|---|---|
| `POST` | `/credores/criar/` | `pagamentos.acesso_backoffice` | Cadastra novo credor | `detalhe_credor(pk)` |
| `POST` | `/credores/<pk>/editar/` | `pagamentos.acesso_backoffice` | Atualiza dados cadastrais e bancários | `detalhe_credor(pk)` |

---

## Referência Automática de Módulos

::: commons

::: credores

::: fiscal

::: pagamentos

::: suprimentos

::: verbas_indenizatorias
