# Guia de Interface: Pagamentos (Operador de Contas a Pagar)

Este guia descreve a tramitação completa do processo de pagamento no PaGé, com foco no perfil **Operador de Contas a Pagar**: da criação até o arquivamento.

Use este documento como roteiro prático de execução diária, incluindo as telas envolvidas, as ações esperadas e os status de entrada e saída de cada etapa.

**Navegação relacionada:** para a especificação técnica detalhada da esteira e das regras de exceção, consulte [Fluxo: Pagamentos](pagamentos.md).

---

## 1. Visão geral da esteira

Fluxo principal (sem devoluções):

`A EMPENHAR` -> `AGUARDANDO LIQUIDAÇÃO` -> `A PAGAR - PENDENTE AUTORIZAÇÃO` -> `A PAGAR - ENVIADO PARA AUTORIZAÇÃO` -> `A PAGAR - AUTORIZADO` -> `LANÇADO - AGUARDANDO COMPROVANTE` -> `PAGO - EM CONFERÊNCIA` -> `PAGO - A CONTABILIZAR` -> `CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL` -> `APROVADO - PENDENTE ARQUIVAMENTO` -> `ARQUIVADO`

---

## 2. Perfil e permissões

Permissão operacional principal para este guia:

- `pagamentos.operador_contas_a_pagar`

Permissões relacionadas em etapas de apoio:

- `pagamentos.operador_contas_a_pagar` (operações de contas a pagar, empenho, lançamento e comprovantes)
- `pagamentos.pode_autorizar_pagamento` (autorização, quando aplicável ao usuário)
- `pagamentos.pode_contabilizar` (contabilização)
- `pagamentos.pode_auditar_conselho` (conselho)
- `pagamentos.pode_arquivar` (arquivamento)

Observação: no dia a dia, o operador normalmente executa a trilha até conferência e encaminha para os perfis de aprovação/controle das etapas seguintes.

---

## 3. Etapa a etapa: criação ao arquivamento

## 3.1 Criar processo

**Tela:** `add_process_view`  
**Ação:** `add_process_action`

### O que preencher na interface

- Credor
- Tipo de pagamento
- Datas e valores da capa
- Indicação de `trigger_a_empenhar`

### Resultado esperado

- Com trigger: processo inicia em `A EMPENHAR`
- Sem trigger: processo inicia em `A PAGAR - PENDENTE AUTORIZAÇÃO`

### Boas práticas

- Validar dados da capa antes de salvar para evitar retrabalho nas etapas de autorização.
- Usar o hub de edição logo após a criação para completar documentos e pendências.

---

## 3.2 Hub de edição (Command Center)

**Tela:** `editar_processo`  
**Template:** `pagamentos/editar_processo_hub.html`

### Como usar

- Navegue pelos cartões/spokes para completar dados sem misturar etapas:
  - Capa
  - Documentos
  - Pendências
  - Liquidações e retenções

### Resultado esperado

- Processo preparado para avançar sem bloqueios de turnpike.

---

## 3.3 Empenho

**Tela:** `a_empenhar_view`

### Entrada

- Status `A EMPENHAR`

### Ações do operador

- Registrar dados de empenho (manual ou importação SISCAC)
- Conferir documento orçamentário obrigatório (quando aplicável)

### Saída

- Processo avança para `AGUARDANDO LIQUIDAÇÃO`

---

## 3.4 Liquidação e ateste

**Tela:** `painel_liquidacoes_view`  
**Spoke:** `documentos_fiscais_view`  
**Ação de ateste:** `alternar_ateste_nota_action`

### Entrada

- Status `AGUARDANDO LIQUIDAÇÃO`

### Ações do operador

- Associar documentos fiscais
- Registrar dados da nota fiscal e retenções
- Atestar notas fiscais

### Turnpike de avanço

- Todas as NFs devem estar atestadas
- Valores precisam estar consistentes

### Saída

- `avancar_para_pagamento_action` leva para `A PAGAR - PENDENTE AUTORIZAÇÃO`

---

## 3.5 Contas a pagar e envio para autorização

**Tela:** `contas_a_pagar`

### Entrada

- Status `A PAGAR - PENDENTE AUTORIZAÇÃO`

### Ações do operador

- Filtrar fila por data, forma e conta
- Revisar pendências e retenções
- Enviar processo(s) para autorização

### Saída

- `A PAGAR - ENVIADO PARA AUTORIZAÇÃO`

---

## 3.6 Autorização

**Tela:** `painel_autorizacao_view`

### Entrada

- Status `A PAGAR - ENVIADO PARA AUTORIZAÇÃO`

### Possíveis resultados

- Aprovado: `A PAGAR - AUTORIZADO`
- Recusado: retorna para `A PAGAR - PENDENTE AUTORIZAÇÃO`

### Orientação para o operador

- Ao recusar, tratar pendência apontada e reenviar para autorização.

---

## 3.7 Lançamento bancário

**Telas/Ações:** `lancamento_bancario`, `marcar_como_lancado_action`

### Entrada

- Status `A PAGAR - AUTORIZADO`

### Ações do operador

- Selecionar processos da rodada de pagamento
- Conferir instruções por forma de pagamento (PIX/TED/boleto/remessa)
- Marcar como lançado

### Saída

- `LANÇADO - AGUARDANDO COMPROVANTE`

### Exceção

- Desfazer lançamento retorna para `A PAGAR - AUTORIZADO`

---

## 3.8 Upload e vínculo de comprovantes

**Tela:** `painel_comprovantes_view`  
**Ação:** `vincular_comprovantes_action`

### Entrada

- Status `LANÇADO - AGUARDANDO COMPROVANTE`

### Ações do operador

- Enviar arquivo(s) de comprovante
- Confirmar vínculo do comprovante ao processo correto

### Efeito de sistema

- Cria documentos de processo e metadados do comprovante
- Atualiza `data_pagamento`

### Saída

- `PAGO - EM CONFERÊNCIA`

---

## 3.9 Conferência pós-pagamento

**Telas:** `painel_conferencia_view`, `conferencia_processo_view`

### Entrada

- Status `PAGO - EM CONFERÊNCIA`

### Ações do operador

- Revisar pendências remanescentes, retenções e anexos
- Corrigir inconsistências permitidas
- Aprovar conferência

### Saída

- `PAGO - A CONTABILIZAR`

---

## 3.10 Contabilização

**Telas:** `painel_contabilizacao_view`, `contabilizacao_processo_view`

### Entrada

- Status `PAGO - A CONTABILIZAR`

### Resultado

- Aprovado: `CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL`
- Recusado: retorna para `PAGO - EM CONFERÊNCIA`

### Orientação para o operador

- Em recusa, revisar apontamentos na conferência e reencaminhar.

---

## 3.11 Conselho fiscal

**Telas:** `painel_conselho_view`, `analise_reuniao_view`, `conselho_processo_view`

### Entrada

- Status `CONTABILIZADO - PARA APRECIAÇÃO DE CONSELHO FISCAL`

### Resultado

- Aprovado em reunião: `APROVADO - PENDENTE ARQUIVAMENTO`
- Recusado: retorna para `PAGO - A CONTABILIZAR`

---

## 3.12 Arquivamento

**Telas/Ações:** `painel_arquivamento_view`, `arquivar_processo_action`

### Entrada

- Status `APROVADO - PENDENTE ARQUIVAMENTO`

### Ações

- Validar documentação final
- Executar arquivamento definitivo

### Saída

- Status final `ARQUIVADO`

---

## 4. Exceções operacionais críticas

## 4.1 Cancelamento do processo

**Spoke:** `cancelar_processo_spoke_view`  
**Ação:** `cancelar_processo_action`

- Justificativa obrigatória
- Em processo pago ou posterior, exige dados de devolução
- Resultado: `CANCELADO / ANULADO`

Consulte também: [Fluxo de Cancelamento](cancelamento.md).

## 4.2 Devolução processual

Quando houver devolução de valores, registrar:

- Valor devolvido
- Data da devolução
- Comprovante da devolução

Registro é realizado de forma transacional com o cancelamento quando aplicável.

## 4.3 Contingência

Retificações formais após criação do processo tramitam em aprovação multi-etapa e não substituem o fluxo padrão de pagamento.

---

## 5. Checklist rápido do operador (uso diário)

1. Criar processo com capa completa e status inicial correto.
2. Garantir empenho/documentação orçamentária quando exigido.
3. Confirmar notas fiscais atestadas e retenções consistentes.
4. Enviar para autorização e tratar recusas com rapidez.
5. Executar lançamento e anexar comprovantes sem divergência.
6. Concluir conferência e monitorar retorno de contabilização/conselho.
7. Encaminhar para arquivamento somente com dossiê completo.

---

## 6. Referências internas

- Fluxo técnico completo: [Fluxo: Pagamentos](pagamentos.md)
- Fluxo de exceção: [Fluxo: Cancelamento](cancelamento.md)
- RBAC e perfil: [Matriz de Permissões](../governanca/matriz_permissoes.md)
