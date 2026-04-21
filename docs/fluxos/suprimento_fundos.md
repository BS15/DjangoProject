# Fluxo: Suprimento de Fundos

Este documento descreve o ciclo completo de um suprimento de fundos no PaGé — da concessão ao encerramento da prestação de contas — e sua integração com a esteira de pagamentos.

---

## 1. Modelo de domínio

`SuprimentoDeFundos` (`suprimentos/models.py`) representa o adiantamento concedido a um servidor (suprido) para pagamento de despesas miúdas ou urgentes.

Campos principais:

| Campo | Descrição |
|-------|-----------|
| `suprido` | Credor (servidor) beneficiário do adiantamento |
| `lotacao` | Unidade administrativa de referência |
| `valor_liquido` | Valor efetivamente recebido pelo suprido |
| `taxa_saque` | Taxa de operação financeira (somada no processo vinculado) |
| `inicio_periodo` / `fim_periodo` | Período de execução das despesas |
| `data_recibo` | Data do recibo de concessão |
| `processo` | FK para `Processo` de pagamento criado automaticamente |
| `status` | `ABERTO` → `ENCERRADO` |

### Domain Seal

Quando o processo vinculado está em estágio `PAGO` ou posterior, mutações em campos sensíveis do suprimento e suas despesas são bloqueadas. O `SealedMutationQuerySet` também impede `update()`, `bulk_update()` e `bulk_create()` para forçar a trilha canônica via save/clean.

---

## 2. Cadastro (concessão)

**View:** `add_suprimento_view` / **Action:** `add_suprimento_action`  
**Permissão:** `suprimentos.acesso_backoffice`

Dentro de uma única transação atômica (`_persistir_suprimento_com_processo`):

1. Suprimento salvo com status `ABERTO`.
2. `criar_processo_para_suprimento` cria um `Processo` vinculado:
   - credor = `suprimento.suprido`,
   - `valor_bruto` = `valor_liquido + taxa_saque`,
   - `valor_liquido` = `valor_liquido`,
   - tipo pagamento = **SUPRIMENTO DE FUNDOS**,
   - status = **A EMPENHAR**.
3. `suprimento.processo` é atualizado com o FK do novo processo.

A partir daí, o processo de pagamento segue a esteira normal de pagamentos (empenho → liquidação → ...).

---

## 3. Gerenciamento operacional

**View:** `gerenciar_suprimento_view`  
**Permissão:** `suprimentos.acesso_backoffice`

Exibe:
- Dados do suprimento (suprido, lotação, período, valores).
- Lista de despesas registradas.
- Indicador de editabilidade (`pode_editar = not _suprimento_encerrado`).

---

## 4. Registro de despesas

**View:** `adicionar_despesa_view` / **Action:** `adicionar_despesa_action`

- Guard: bloqueia inclusão de novas despesas quando suprimento estiver `ENCERRADO`.
- Para cada despesa, `DespesaSuprimento` recebe: data, estabelecimento, CNPJ/CPF, número de NF, detalhamento, valor e arquivo comprobatório.
- Validação via `DespesaSuprimentoForm` (formulário ModelForm com campos obrigatórios).

---

## 5. Fechamento da prestação de contas

**Action:** `fechar_suprimento_action`  
**Permissão:** `suprimentos.acesso_backoffice`

`_atualizar_status_apos_fechamento` executa dentro de uma transação:

1. Status do `Processo` vinculado é definido diretamente como **`PAGO - EM CONFERÊNCIA`**.
2. `gerar_documentos_automaticos_processo` é acionado para a transição, permitindo que hooks de documentação automática sejam executados.
3. Status do suprimento muda para **`ENCERRADO`**.

!!! warning "Integração direta de status"
    Ao fechar o suprimento, o processo vinculado pula etapas intermediárias de pagamento e vai direto para `PAGO - EM CONFERÊNCIA`. Isso é intencional: o suprimento representa uma modalidade em que o pagamento já ocorreu antecipadamente ao suprido. A conferência valida a prestação de contas ex-post.

A partir desse ponto, o processo segue a esteira pós-pagamento normal:

```
PAGO - EM CONFERÊNCIA → PAGO - A CONTABILIZAR → CONTABILIZADO... → APROVADO... → ARQUIVADO
```

---

## 6. Geração de documentos

O serviço `gerar_e_anexar_recibo_suprimento` (`suprimentos/services/documentos.py`):

1. Gera o PDF do recibo via `gerar_documento_bytes`.
2. Cria `DocumentoSuprimentoDeFundos` com o arquivo.
3. Cria um rascunho de assinatura eletrônica (`AssinaturaEletronica`) via `criar_assinatura_rascunho`.

---

## 7. Validações de negócio

As regras do regime de suprimento são verificadas em `validar_regras_suprimento` (`pagamentos/validators.py`), chamado no `clean()` do `SuprimentoForm`. Erros são propagados por campo para exibição no formulário.

---

## Referências de código

| Componente | Localização |
|-----------|------------|
| Modelo | `suprimentos/models.py` |
| Cadastro (GET) | `suprimentos/views/cadastro/panels.py` |
| Cadastro (POST) | `suprimentos/views/cadastro/actions.py` |
| Painel / despesas / fechamento (GET) | `suprimentos/views/prestacao_contas/panels.py` |
| Ações despesas / fechamento (POST) | `suprimentos/views/prestacao_contas/actions.py` |
| Helpers internos | `suprimentos/views/helpers.py` |
| Integração com Processo | `suprimentos/services/processo_integration.py` |
| Geração de documentos | `suprimentos/services/documentos.py` |
| Validações de negócio | `pagamentos/validators.py` |
