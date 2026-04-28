# Fluxo: Diárias

Este documento descreve o ciclo operacional completo de uma [diária](/negocio/glossario_conselho.md#diaria) no PaGé — do cadastro ao encerramento da prestação de contas — incluindo vínculo com processo de pagamento, assinatura eletrônica, devolução e contingência.

Para o padrão arquitetural aplicado nas views deste fluxo, consulte [Padrão Manager-Worker](../arquitetura/manager_worker.md) e [Interface Hub-and-Spoke](../arquitetura/hub_spoke.md).

---

## Diagrama de workflow (visão macro)

```mermaid
stateDiagram-v2
    [*] --> RASCUNHO : add_diaria_action (_preparar_nova_diaria)
    RASCUNHO --> SOLICITADA : solicitar_autorizacao_diaria_action
    SOLICITADA --> APROVADA : autorizar_diaria_action
    APROVADA --> VINCULADA_A_PROCESSO : vincular_diaria_processo_action
    RASCUNHO --> CANCELADA_ANULADA : cancelar_diaria_action
    SOLICITADA --> CANCELADA_ANULADA : cancelar_diaria_action
    APROVADA --> CANCELADA_ANULADA : cancelar_diaria_action
    VINCULADA_A_PROCESSO --> PRESTACAO_ABERTA : obter_ou_criar_prestacao
    PRESTACAO_ABERTA --> PRESTACAO_ENCERRADA : encerrar_prestacao_action
    PRESTACAO_ENCERRADA --> PRESTACAO_ACEITA : aceitar_prestacao_action
    PRESTACAO_ACEITA --> PROCESSO_PAGO_ESTEIRA_POSTERIOR : segue esteira de pagamentos
    PROCESSO_PAGO_ESTEIRA_POSTERIOR --> [*]
    CANCELADA_ANULADA --> [*]
```

---

## 1. Modelo de domínio

`Diaria` (`verbas_indenizatorias/models.py`) é a entidade central. Ao ser salva, o modelo:

- Recalcula `quantidade_diarias` automaticamente pelo intervalo de datas e tipo.
- Recalcula `valor_total` com base na tabela `Tabela_Valores_Unitarios_Verbas_Indenizatorias` para o cargo/função do beneficiário.
- Chama `full_clean()` antes de persistir, verificando conflitos de período e regras de complementação.

### Domain Seal (pós-pagamento)

Quando a diária está vinculada a um [processo](/negocio/glossario_conselho.md#processo) em estágio `PAGO` ou posterior, mutações diretas em campos sensíveis são bloqueadas em `save()` e `delete()`. A única exceção autorizada é via **[Contingência](/negocio/glossario_conselho.md#contingencia) aprovada** com bypass controlado (`_bypass_domain_seal = True`).

Contexto arquitetural do Domain Seal e [turnpikes](/negocio/glossario_conselho.md#turnpike): [Domain Knowledge](../arquitetura/domain_knowledge.md).

### Campos protegidos pós-pagamento

`beneficiario`, `proponente`, `tipo_solicitacao`, `data_saida`, `data_retorno`, `cidades`, `objetivo`, `quantidade_diarias`, `valor_total`, `meio_de_transporte`, `autorizada`, `numero_siscac`, `processo`.

---

## 2. Criação

**View:** `add_diaria_view` / **Action:** `add_diaria_action`  
**Permissão:** `pagamentos.pode_criar_diarias`

Referência de permissão e RBAC: [Matriz de Permissões](../governanca/matriz_permissoes.md).

1. Operador preenche o formulário (`DiariaForm`).
2. `_preparar_nova_diaria` define a diária como **rascunho** (`autorizada=False`, status `RASCUNHO`).
3. Se tipo for `COMPLEMENTACAO`, o sistema gera e anexa o **SCD** (Solicitação de Complementação de Diária).
4. Redirecionamento para `gerenciar_diaria`.

### Entrada alternativa: diária com solicitação já assinada (skip SCD)

**View:** `add_diaria_assinada_view` / **Action:** `add_diaria_assinada_action`  
**Permissão:** `pagamentos.pode_criar_diarias`

Use esta trilha quando a solicitação já estiver assinada fora do fluxo eletrônico padrão.

1. Operador preenche o mesmo formulário base e anexa o PDF da solicitação assinada (`solicitacao_assinada_arquivo`).
2. A diária nasce **pré-aprovada** (`status=APROVADA`, `autorizada=True`).
3. O sistema **não gera SCD** e **não dispara envio de SCD para assinatura**.
4. O arquivo enviado é anexado como documento SCD para rastreabilidade.
5. O sistema gera automaticamente o **PCD** após a confirmação da inclusão.

### Etapas de autorização

Após o cadastro, a diária segue o fluxo explícito de autorização:

1. `solicitar_autorizacao_diaria_action`: `RASCUNHO → SOLICITADA`.
2. `autorizar_diaria_action`: `SOLICITADA → APROVADA` (e marca `autorizada=True`), apenas quando o usuário autenticado é o `proponente` da diária.

No modo de solicitação já assinada, essas duas etapas não são necessárias, pois a diária já é persistida como `APROVADA`.

### Criação em lote com switch de solicitação já assinada

**View:** `importar_diarias_view`  
**Serviço:** `confirmar_diarias_lote_com_modo`

Padrão de delegação Action/Service: [Padrão Manager-Worker](../arquitetura/manager_worker.md).

Na tela de importação em lote existe o switch **"Entrada com solicitação já assinada"**.

- **Switch desligado (modo padrão):** cria diária para trilha de autorização (`status=SOLICITADA`, `autorizada=False`).
- **Switch ligado (modo já assinada):** cria diária como pré-aprovada (`status=APROVADA`, `autorizada=True`) e gera **PCD** automaticamente na confirmação.

Importante: no lote, o switch altera o modo de criação da diária, mas não anexa PDF de solicitação assinada por linha. Para anexar o PDF da solicitação assinada na própria criação, use a entrada individual `add_diaria_assinada`.

---

## 3. Hub de gerenciamento

**View:** `gerenciar_diaria_view`  
**Permissão:** `pagamentos.pode_gerenciar_diarias`

Exibe:
- Dados da diária (status, beneficiário, datas, valor calculado).
- Prestação de contas com comprovantes.
- Spokes de ação (cartões de navegação):

| Spoke | Finalidade |
|-------|-----------|
| `vinculo_diaria_spoke` | Vincular/desvincular do processo de pagamento |
| `devolucao_diaria_spoke` | Registrar devolução parcial de valor |
| `apostila_diaria_spoke` | Apostilar correções formais |
| `cancelar_diaria_spoke` | Cancelar/anular a diária |

---

## 4. Vínculo com processo de pagamento

**Action:** `vincular_diaria_processo_action` / `desvincular_diaria_processo_action`

Regras:
- Vínculo e desvínculo permitidos **somente** enquanto o processo estiver em status pré-autorização (`STATUS_PROCESSO_PRE_AUTORIZACAO`).
- Após vínculo, `_recalcular_totais_processo_verbas` sincroniza os valores bruto/líquido do processo somando diárias + reembolsos + jetons + auxílios.
- O tipo de pagamento do processo é forçado para **VERBAS INDENIZATÓRIAS**.
- O campo `extraorcamentario` do processo é zerado automaticamente.

---

## 5. Prestação de contas

### Ciclo do beneficiário

1. `PrestacaoContasDiaria` é criada automaticamente ao primeiro acesso (`obter_ou_criar_prestacao`), com status `ABERTA`.
2. Beneficiário (ou operador com permissão `operar_prestacao_contas`) registra comprovantes via `registrar_comprovante_action`.
3. Ao encerrar (`encerrar_prestacao_action`): status muda para `ENCERRADA`, metadados de encerramento são gravados, e o **Termo de Prestação** é gerado e anexado automaticamente.

### Revisão pela equipe interna

**Views:** `painel_revisar_prestacoes_view` / `revisar_prestacao_view`  
**Permissão:** `verbas_indenizatorias.analisar_prestacao_contas`

Requisitos de trilha e evidência de mudança: [Trilha de Auditoria](../governanca/trilha_auditoria.md).

- O analista revisa os comprovantes do beneficiário.
- `aceitar_prestacao_action`:
  - Exige que a diária esteja vinculada a um processo.
  - Replica todos os `DocumentoComprovacao` como `DocumentoProcesso` no processo.
  - Encerra a prestação.
  - Gera o Termo de Prestação.

---

## 6. Assinatura eletrônica (Autentique)

**Action:** `aprovar_revisao_solicitacao_action` (quando `tipo_verba=diaria`)  
**Permissão:** `pagamentos.operador_contas_a_pagar`

1. Na aprovação da revisão operacional da diária (`APROVADA -> REVISADA`), o sistema emite/recupera o PCD.
2. Envia o PDF para a Autentique via `enviar_documento_para_assinatura`.
3. Grava `autentique_id`, `autentique_url` e status `PENDENTE` na assinatura.
4. O fluxo não é mais disparado no hub `gerenciar_diaria`.

**Sincronização:** `sincronizar_assinatura_view` verifica o status na Autentique e baixa o PDF assinado quando disponível.  
**Reenvio:** `reenviar_assinatura_view` reenvia o rascunho SCD para nova rodada de assinaturas.

---

## 7. Devolução

**Views:** `painel_devolucoes_diarias_view` / `registrar_devolucao_diaria_view`  
**Action:** `registrar_devolucao_diaria_action`

- Cria um registro `DevolucaoDiaria` vinculado à diária, com data, valor e motivo.
- `clean()` valida que `valor_devolvido` não exceda `diaria.valor_total`.
- **Não altera** o valor total da diária diretamente; a devolução é um registro paralelo para rastreabilidade auditável.

---

## 8. Contingência

**Views:** `painel_contingencias_diarias_view` / `add_contingencia_diaria_view`  
**Actions:** `add_contingencia_diaria_action` / `analisar_contingencia_diaria_action`

### Ciclo de vida

```
PENDENTE_SUPERVISOR → APROVADA (campo aplicado à diária)
                   → REJEITADA (sem efeito na diária)
```

### Campos permitidos para retificação via contingência

`numero_siscac`, `cidade_origem`, `cidade_destino`, `objetivo`, `proponente_id`, `meio_de_transporte_id`

### Aplicação

Ao aprovar, `_aplicar_contingencia_diaria` usa `_bypass_domain_seal = True` para permitir a mutação do campo específico mesmo com processo selado. O bypass é garantidamente removido após o `save()` via bloco `try/finally`.

---

## 9. Cancelamento

**Spoke (GET):** `cancelar_diaria_spoke_view`  
**Action (POST):** `cancelar_diaria_action`  
**Permissão:** `pagamentos.pode_gerenciar_diarias`  
**Serviço:** `cancelar_verba` (`pagamentos/services/cancelamentos.py`)

- Justificativa é sempre obrigatória.
- **Quando a diária está com `status_choice == "PAGA"`**, o formulário exige os dados de devolução correspondente (valor, data e comprovante). A `DevolucaoProcessual` é criada atomicamente na mesma transação.
- A transação atômica:
  1. Cria `DevolucaoProcessual` no processo vinculado (se paga).
  2. Define status do processo como `CANCELADO / ANULADO`.
  3. Define status da diária como `CANCELADO / ANULADO` e `autorizada=False`.
  4. Grava `CancelamentoProcessual` (tipo `DIARIA`).

Consulte o [Fluxo de Cancelamento](cancelamento.md) para a especificação completa, incluindo o partial compartilhado de devolução.

Para o fluxo financeiro após agrupamento e pagamento, veja [Fluxo: Pagamentos](pagamentos.md).

---

## Referências de código

| Componente | Localização |
|-----------|------------|
| Modelos | `verbas_indenizatorias/models.py` |
| Painel / spokes (GET) | `verbas_indenizatorias/views/diarias/panels.py` |
| Ações principais (POST) | `verbas_indenizatorias/views/diarias/actions.py` |
| Devolução | `verbas_indenizatorias/views/diarias/devolucao/` |
| Contingência | `verbas_indenizatorias/views/diarias/contingencia/` |
| Assinaturas | `verbas_indenizatorias/views/diarias/signatures.py` |
| Serviço de prestação | `verbas_indenizatorias/services/prestacao.py` |
| Serviço de vínculo | `verbas_indenizatorias/services/vinculos_diaria.py` |
| Serviço de contingência | `verbas_indenizatorias/services/contingencia.py` |
