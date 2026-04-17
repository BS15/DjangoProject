# Dicionários Operacionais

Este documento contém o catálogo operacional por action: uma entrada por endpoint, com contrato objetivo para manutenção, auditoria e revisão de segurança.

## Convenção do catálogo

Campos usados em cada entrada:
- Action
- Arquivo
- Rota (nome e path)
- Permissão
- Método
- Entrada
- Validações
- Worker
- Efeitos
- Redirect
- Feedback

## Catálogo de Actions Fiscais

### agrupar_retencoes_action

| Campo | Valor |
|---|---|
| Action | `agrupar_retencoes_action` |
| Arquivo | `fiscal/views/impostos/actions.py` |
| Rota | `agrupar_retencoes_action` (`/impostos/agrupar/`) |
| Permissão | `fiscal.acesso_backoffice` |
| Método | `POST` |
| Entrada | `retencao_ids` (fallback: `itens_selecionados`) |
| Validações | exige seleção; soma de retenções deve ser maior que zero |
| Worker | sem worker dedicado (orquestração na própria action) |
| Efeitos | cria `Processo` de recolhimento e atualiza `RetencaoImposto.processo_pagamento` |
| Redirect | sucesso: `editar_processo(pk)`; erro: `painel_impostos_view` |
| Feedback | mensagens de warning/success via `messages` |

### agrupar_impostos_action (legado)

| Campo | Valor |
|---|---|
| Action | `agrupar_impostos_action` |
| Arquivo | `fiscal/views/impostos/actions.py` |
| Rota | `agrupar_impostos` (`/impostos/agrupar/legacy/`) |
| Permissão | `fiscal.acesso_backoffice` |
| Método | `POST` |
| Entrada | idêntica à `agrupar_retencoes_action` |
| Validações | delegadas para `agrupar_retencoes_action` |
| Worker | delega para `agrupar_retencoes_action` |
| Efeitos | iguais ao endpoint principal |
| Redirect | igual ao endpoint principal |
| Feedback | igual ao endpoint principal |

### anexar_documentos_retencoes_action

| Campo | Valor |
|---|---|
| Action | `anexar_documentos_retencoes_action` |
| Arquivo | `fiscal/views/impostos/actions.py` |
| Rota | `anexar_documentos_retencoes_action` (`/impostos/anexar-documentos/`) |
| Permissão | `fiscal.acesso_backoffice` |
| Método | `POST` |
| Entrada | `retencao_ids`, `guia_arquivo`, `comprovante_arquivo`, `mes_referencia`, `ano_referencia` |
| Validações | exige seleção, guia e comprovante, competência válida e retenções elegíveis já agrupadas |
| Worker | `anexar_guia_comprovante_relatorio_em_processos(...)` |
| Efeitos | anexa guia, comprovante e relatório mensal por processo de recolhimento |
| Redirect | `painel_impostos_view` |
| Feedback | mensagens de error/success via `messages` |

### gerar_lote_reinf_action

| Campo | Valor |
|---|---|
| Action | `gerar_lote_reinf_action` |
| Arquivo | `fiscal/views/reinf/actions.py` |
| Rota | `gerar_lote_reinf_action` (`/reinf/gerar-lotes/`) |
| Permissão | `fiscal.acesso_backoffice` |
| Método | `POST` |
| Entrada | `competencia` (formatos `MM/AAAA` ou `AAAA-MM`) |
| Validações | normaliza competência e usa mês/ano atual em fallback |
| Worker | `fiscal.services.gerar_lotes_reinf` |
| Efeitos | gera XMLs de lotes EFD-Reinf e devolve zip em resposta HTTP |
| Redirect | não aplica (retorna arquivo) |
| Feedback | erro funcional via `HttpResponse` 404 quando não há lotes |

### transmitir_lote_reinf_action

| Campo | Valor |
|---|---|
| Action | `transmitir_lote_reinf_action` |
| Arquivo | `fiscal/views/reinf/actions.py` |
| Rota | `transmitir_lote_reinf_action` (`/reinf/transmitir-lotes/`) |
| Permissão | `fiscal.acesso_backoffice` |
| Método | `POST` |
| Entrada | sem payload obrigatório |
| Validações | não aplica |
| Worker | placeholder (integração externa ainda não habilitada) |
| Efeitos | sem mutação de dados |
| Redirect | `painel_reinf_view` |
| Feedback | warning de funcionalidade indisponível |

### gerar_lote_reinf_legacy_action (legado)

| Campo | Valor |
|---|---|
| Action | `gerar_lote_reinf_legacy_action` |
| Arquivo | `fiscal/views/reinf/actions.py` |
| Rota | `gerar_lote_reinf` (`/reinf/gerar-lotes/legacy/`) |
| Permissão | `fiscal.acesso_backoffice` |
| Método | `POST` |
| Entrada | competência via parser legado |
| Validações | delegadas para `parse_competencia` |
| Worker | `fiscal.services.gerar_lotes_reinf` |
| Efeitos | gera XMLs e devolve zip |
| Redirect | não aplica (retorna arquivo) |
| Feedback | erro funcional via `HttpResponse` 404 quando não há lotes |

## Catálogo de Actions do Fluxo

### Namespace `pre_payment`

#### Etapa `cadastro`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `add_process_action` | `fluxo/views/pre_payment/cadastro/actions.py` | `add_process_action` (`/adicionar/action/`) | ver decorator da action | `POST` | dados de capa e formsets iniciais | regras de criação e consistência de processo | services/helpers de cadastro quando aplicável | cria processo e registros associados | `editar_processo` | `messages` success/error |
| `editar_processo_capa_action` | `fluxo/views/pre_payment/cadastro/actions.py` | `editar_processo_capa_action` (`/processo/<int:pk>/editar/capa/action/`) | ver decorator da action | `POST` | dados de capa do processo | validação de formulário e status elegível | services/helpers de cadastro quando aplicável | atualiza dados de capa | tela de edição do processo | `messages` success/error |
| `editar_processo_documentos_action` | `fluxo/views/pre_payment/cadastro/actions.py` | `editar_processo_documentos_action` (`/processo/<int:pk>/editar/documentos/action/`) | ver decorator da action | `POST` | payload documental e anexos | regras documentais e de etapa | services/helpers documentais quando aplicável | cria/atualiza documentos e pendências | tela de edição do processo | `messages` success/error |
| `editar_processo_pendencias_action` | `fluxo/views/pre_payment/cadastro/actions.py` | `editar_processo_pendencias_action` (`/processo/<int:pk>/editar/pendencias/action/`) | ver decorator da action | `POST` | atualização de pendências | validação de estado de pendências | helpers de pendência quando aplicável | altera status de pendências | tela de edição do processo | `messages` success/error |

#### Etapa `empenho`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `registrar_empenho_action` | `fluxo/views/pre_payment/empenho/actions.py` | `registrar_empenho_action` (`/a-empenhar/registrar-empenho/`) | ver decorator da action | `POST` | dados de empenho e processo alvo | consistência de valores e elegibilidade | services de empenho quando aplicável | registra dados de empenho no processo | painel/fluxo de empenho | `messages` success/error |

#### Etapa `liquidacoes`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `alternar_ateste_nota_action` | `fluxo/views/pre_payment/liquidacoes/actions.py` | `alternar_ateste_nota` (`/liquidacoes/atestar/<int:pk>/`) | ver decorator da action | `POST` | identificação da nota | valida elegibilidade de ateste | service/helper de liquidação quando aplicável | alterna estado de ateste | painel de liquidações | `messages` success/error |
| `avancar_para_pagamento_action` | `fluxo/views/pre_payment/liquidacoes/actions.py` | `avancar_para_pagamento` (`/processo/<int:pk>/avancar-para-pagamento/`) | ver decorator da action | `POST` | processo alvo | turnpikes de liquidação e obrigatoriedades | service de transição de etapa | avança processo para pagamento | hub do processo/painel | `messages` success/error |

### Namespace `payment`

#### Etapa `contas_a_pagar`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `enviar_para_autorizacao_action` | `fluxo/views/payment/contas_a_pagar/actions.py` | `enviar_para_autorizacao` (`/processos/enviar-autorizacao/`) | ver decorator da action | `POST` | seleção de processos | validação de elegibilidade para autorização | service de contas a pagar | altera estado para autorização | painel de contas a pagar | `messages` success/error |

#### Etapa `autorizacao`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `autorizar_pagamento` | `fluxo/views/payment/autorizacao/actions.py` | `autorizar_pagamento` (`/processos/autorizar-pagamento/`) | ver decorator da action | `POST` | seleção de processos para autorização | valida permissão e critérios de autorização | service de autorização quando aplicável | autoriza pagamento de processos | painel de autorização | `messages` success/error |
| `recusar_autorizacao_action` | `fluxo/views/payment/autorizacao/actions.py` | `recusar_autorizacao` (`/processos/autorizacao/<int:pk>/recusar/`) | ver decorator da action | `POST` | processo e motivo de recusa | validação de estado e permissão | service de recusa quando aplicável | registra recusa e atualiza estado | painel de autorização | `messages` success/error |

#### Etapa `lancamento`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `separar_para_lancamento_bancario_action` | `fluxo/views/payment/lancamento/actions.py` | `separar_para_lancamento_bancario` (`/processos/separar-lancamento/`) | ver decorator da action | `POST` | seleção de processos | validação de status elegível para lançamento | service de lançamento bancário | separa processos para lançamento | painel de lançamento bancário | `messages` success/error |
| `marcar_como_lancado_action` | `fluxo/views/payment/lancamento/actions.py` | `marcar_como_lancado` (`/processos/marcar-lancado/`) | ver decorator da action | `POST` | seleção de processos lançados | validação de lote e estado | service de lançamento bancário | marca processos como lançados | painel de lançamento bancário | `messages` success/error |
| `desmarcar_lancamento_action` | `fluxo/views/payment/lancamento/actions.py` | `desmarcar_lancamento` (`/processos/desmarcar-lancamento/`) | ver decorator da action | `POST` | seleção de processos | validação de reversão permitida | service de lançamento bancário | reverte marcação de lançamento | painel de lançamento bancário | `messages` success/error |

### Namespace `post_payment`

#### Etapa `conferencia`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `iniciar_conferencia_action` | `fluxo/views/post_payment/conferencia/actions.py` | `iniciar_conferencia` (`/processos/conferencia/iniciar/`) | ver decorator da action | `POST` | seleção de processos | valida elegibilidade para conferência | service de conferência quando aplicável | move processos para revisão de conferência | painel de conferência | `messages` success/error |
| `aprovar_conferencia_action` | `fluxo/views/post_payment/conferencia/actions.py` | `aprovar_conferencia` (`/processos/conferencia/<int:pk>/aprovar/`) | ver decorator da action | `POST` | processo alvo | valida checklist da etapa | service de conferência quando aplicável | aprova conferência e avança fluxo | painel de conferência | `messages` success/error |

#### Etapa `contabilizacao`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `iniciar_contabilizacao_action` | `fluxo/views/post_payment/contabilizacao/actions.py` | `iniciar_contabilizacao` (`/processos/contabilizacao/iniciar/`) | ver decorator da action | `POST` | seleção de processos | valida elegibilidade para contabilização | service de contabilização quando aplicável | inicia etapa de contabilização | painel de contabilização | `messages` success/error |
| `aprovar_contabilizacao_action` | `fluxo/views/post_payment/contabilizacao/actions.py` | `aprovar_contabilizacao` (`/processos/contabilizacao/<int:pk>/aprovar/`) | ver decorator da action | `POST` | processo alvo | valida regras da etapa | service de contabilização quando aplicável | aprova contabilização | painel de contabilização | `messages` success/error |
| `recusar_contabilizacao_action` | `fluxo/views/post_payment/contabilizacao/actions.py` | `recusar_contabilizacao` (`/processos/contabilizacao/<int:pk>/recusar/`) | ver decorator da action | `POST` | processo e justificativa | valida recusa permitida | service de contabilização quando aplicável | recusa contabilização e ajusta estado | painel de contabilização | `messages` success/error |

#### Etapa `conselho`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `aprovar_conselho_action` | `fluxo/views/post_payment/conselho/actions.py` | `aprovar_conselho` (`/processos/conselho/<int:pk>/aprovar/`) | ver decorator da action | `POST` | processo em análise de conselho | validações de deliberação | service de conselho quando aplicável | aprova deliberação | painel de conselho | `messages` success/error |
| `recusar_conselho_action` | `fluxo/views/post_payment/conselho/actions.py` | `recusar_conselho` (`/processos/conselho/<int:pk>/recusar/`) | ver decorator da action | `POST` | processo e justificativa | validações de recusa | service de conselho quando aplicável | recusa deliberação | painel de conselho | `messages` success/error |

#### Etapa `reunioes`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `gerenciar_reunioes_action` | `fluxo/views/post_payment/reunioes/actions.py` | `gerenciar_reunioes_action` (`/processos/conselho/reunioes/criar/`) | ver decorator da action | `POST` | dados da reunião | validações de criação de reunião | service de reuniões quando aplicável | cria/atualiza reunião | painel de reuniões | `messages` success/error |
| `montar_pauta_reuniao_action` | `fluxo/views/post_payment/reunioes/actions.py` | `montar_pauta_reuniao_action` (`/processos/conselho/reunioes/<int:reuniao_id>/montar-pauta/adicionar/`) | ver decorator da action | `POST` | itens da pauta e reunião alvo | validações de elegibilidade dos processos | service de reuniões quando aplicável | vincula itens na pauta | tela de pauta da reunião | `messages` success/error |
| `iniciar_conselho_reuniao_action` | `fluxo/views/post_payment/reunioes/actions.py` | `iniciar_conselho_reuniao` (`/processos/conselho/reunioes/<int:reuniao_id>/iniciar/`) | ver decorator da action | `POST` | reunião alvo | validações de prontidão da pauta | service de reuniões quando aplicável | inicia sessão de conselho | análise de reunião/painel | `messages` success/error |

#### Etapa `arquivamento`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `arquivar_processo_action` | `fluxo/views/post_payment/arquivamento/actions.py` | `arquivar_processo_action` (`/processos/arquivamento/<int:pk>/executar/`) | ver decorator da action | `POST` | processo alvo | validações de encerramento e completude | service de arquivamento quando aplicável | arquiva processo | painel de arquivamento | `messages` success/error |

### Namespace `support`

#### Etapa `pendencia`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `atualizar_pendencias_lote_action` | `fluxo/views/support/pendencia/actions.py` | `painel_pendencias_action` (`/pendencias/action/`) | ver decorator da action | `POST` | lote de pendências e status | validação de lote e transições permitidas | helper/service de pendência | atualiza múltiplas pendências | painel de pendências | `messages` success/error |

#### Etapa `devolucao`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `registrar_devolucao_action` | `fluxo/views/support/devolucao/actions.py` | `registrar_devolucao_action` (`/processo/<int:processo_id>/devolucao/salvar/`) | ver decorator da action | `POST` | dados da devolução e processo | validações de devolução e anexos | service de devolução quando aplicável | registra devolução financeira/documental | painel de devoluções/processo | `messages` success/error |

#### Etapa `contingencia`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `add_contingencia_action` | `fluxo/views/support/contingencia/actions.py` | `add_contingencia_action` (`/contingencias/nova/enviar/`) | ver decorator da action | `POST` | dados de contingência | validação de elegibilidade e campos obrigatórios | service/helper de contingência | cria contingência vinculada ao processo | painel de contingências | `messages` success/error |
| `analisar_contingencia_action` | `fluxo/views/support/contingencia/actions.py` | `analisar_contingencia` (`/contingencias/<int:pk>/analisar/`) | ver decorator da action | `POST` | decisão sobre contingência | validação de estado e permissão | service/helper de contingência | aprova/recusa contingência e atualiza estado | painel de contingências | `messages` success/error |

#### Etapa `contas_fixas`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `add_conta_fixa_action` | `fluxo/views/support/contas_fixas/actions.py` | `add_conta_fixa_action` (`/contas-fixas/nova/action/`) | ver decorator da action | `POST` | dados da conta fixa | validação de formulário | service/helper de contas fixas | cria conta/fatura | painel de contas fixas | `messages` success/error |
| `edit_conta_fixa_action` | `fluxo/views/support/contas_fixas/actions.py` | `edit_conta_fixa_action` (`/contas-fixas/<int:pk>/editar/action/`) | ver decorator da action | `POST` | atualização de conta fixa | validação de formulário | service/helper de contas fixas | atualiza conta/fatura | painel de contas fixas | `messages` success/error |
| `vincular_processo_fatura_action` | `fluxo/views/support/contas_fixas/actions.py` | `vincular_processo_fatura` (`/contas-fixas/<int:fatura_id>/vincular/`) | ver decorator da action | `POST` | fatura e processo alvo | validação de vínculo permitido | service/helper de contas fixas | vincula fatura a processo | painel de contas fixas | `messages` success/error |
| `excluir_conta_fixa_action` | `fluxo/views/support/contas_fixas/actions.py` | `excluir_conta_fixa` (`/contas-fixas/<int:pk>/excluir/`) | ver decorator da action | `POST` | conta fixa alvo | validação de exclusão permitida | service/helper de contas fixas | remove/desativa vínculo conforme regra do módulo | painel de contas fixas | `messages` success/error |

## Catálogo de Actions de Verbas Indenizatórias

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `editar_processo_verbas_capa_action` | `verbas_indenizatorias/views/processo/actions.py` | `editar_processo_verbas_capa_action` (`/processo/<int:pk>/editar-verbas/capa/action/`) | ver decorator da action | `POST` | dados de capa do processo de verbas | validação de formulário | services/helpers de processo de verbas | atualiza capa do processo | tela de edição de verbas | `messages` success/error |
| `editar_processo_verbas_pendencias_action` | `verbas_indenizatorias/views/processo/actions.py` | `editar_processo_verbas_pendencias_action` (`/processo/<int:pk>/editar-verbas/pendencias/action/`) | ver decorator da action | `POST` | atualização de pendências | validação de transições de pendência | helpers de pendências do módulo | atualiza pendências | tela de edição de verbas | `messages` success/error |
| `editar_processo_verbas_documentos_action` | `verbas_indenizatorias/views/processo/actions.py` | `editar_processo_verbas_documentos_action` (`/processo/<int:pk>/editar-verbas/documentos/action/`) | ver decorator da action | `POST` | dados documentais e anexos | regras documentais da etapa | services/helpers documentais | cria/atualiza documentos | tela de edição de verbas | `messages` success/error |
| `agrupar_verbas_view` | `verbas_indenizatorias/views/processo/actions.py` | `agrupar_verbas` (`/verbas/agrupar/<str:tipo_verba>/`) | ver decorator da action | `POST` | tipo de verba + seleção de itens | validação por tipo de verba | service de agrupamento | agrupa verbas em processo de pagamento | painel de verbas | `messages` success/error |
| `add_diaria_action` | `verbas_indenizatorias/views/diarias/actions.py` | `add_diaria_action` (`/verbas/diarias/nova/action/`) | ver decorator da action | `POST` | dados de diária | validações de beneficiário e período | services/helpers de diárias | cria diária e estado inicial | listas/gerência de diárias | `messages` success/error |
| `registrar_comprovante_action` | `verbas_indenizatorias/views/diarias/actions.py` | `registrar_comprovante_action` (`/verbas/diarias/<int:pk>/comprovantes/registrar/`) | ver decorator da action | `POST` | comprovante e diária alvo | validação de arquivo e estado | helper de comprovantes | anexa comprovante e ajusta estado | gerência da diária | `messages` success/error |
| `cancelar_diaria_action` | `verbas_indenizatorias/views/diarias/actions.py` | `cancelar_diaria_action` (`/verbas/diarias/<int:pk>/cancelar/`) | ver decorator da action | `POST` | diária alvo | validação de cancelamento permitido | service de diárias | cancela diária | listas/gerência de diárias | `messages` success/error |
| `add_reembolso_action` | `verbas_indenizatorias/views/reembolsos/actions.py` | `add_reembolso_action` (`/verbas/reembolsos/novo/action/`) | ver decorator da action | `POST` | dados de reembolso | validações de campos e valores | services/helpers de reembolso | cria reembolso | listas/gerência de reembolsos | `messages` success/error |
| `solicitar_autorizacao_reembolso_action` | `verbas_indenizatorias/views/reembolsos/actions.py` | `solicitar_autorizacao_reembolso_action` (`/verbas/reembolsos/<int:pk>/solicitar-autorizacao/`) | ver decorator da action | `POST` | reembolso alvo | validações de elegibilidade | service de status | altera status para solicitação de autorização | gerência de reembolso | `messages` success/error |
| `autorizar_reembolso_action` | `verbas_indenizatorias/views/reembolsos/actions.py` | `autorizar_reembolso_action` (`/verbas/reembolsos/<int:pk>/autorizar/`) | ver decorator da action | `POST` | reembolso alvo | validações de autorização | service de status | autoriza reembolso | gerência de reembolso | `messages` success/error |
| `cancelar_reembolso_action` | `verbas_indenizatorias/views/reembolsos/actions.py` | `cancelar_reembolso_action` (`/verbas/reembolsos/<int:pk>/cancelar/`) | ver decorator da action | `POST` | reembolso alvo | validações de cancelamento | service de status | cancela reembolso | gerência de reembolso | `messages` success/error |
| `registrar_comprovante_reembolso_action` | `verbas_indenizatorias/views/reembolsos/actions.py` | `registrar_comprovante_reembolso_action` (`/verbas/reembolsos/<int:pk>/comprovantes/registrar/`) | ver decorator da action | `POST` | comprovante e reembolso alvo | validação de arquivo e elegibilidade | helper de comprovantes | anexa comprovante | gerência de reembolso | `messages` success/error |
| `add_jeton_action` | `verbas_indenizatorias/views/jetons/actions.py` | `add_jeton_action` (`/verbas/jetons/novo/action/`) | ver decorator da action | `POST` | dados de jeton | validações de sessão/beneficiário | services/helpers de jetons | cria jeton | listas/gerência de jetons | `messages` success/error |
| `solicitar_autorizacao_jeton_action` | `verbas_indenizatorias/views/jetons/actions.py` | `solicitar_autorizacao_jeton_action` (`/verbas/jetons/<int:pk>/solicitar-autorizacao/`) | ver decorator da action | `POST` | jeton alvo | validações de elegibilidade | service de status | solicita autorização de jeton | gerência de jeton | `messages` success/error |
| `autorizar_jeton_action` | `verbas_indenizatorias/views/jetons/actions.py` | `autorizar_jeton_action` (`/verbas/jetons/<int:pk>/autorizar/`) | ver decorator da action | `POST` | jeton alvo | validações de autorização | service de status | autoriza jeton | gerência de jeton | `messages` success/error |
| `cancelar_jeton_action` | `verbas_indenizatorias/views/jetons/actions.py` | `cancelar_jeton_action` (`/verbas/jetons/<int:pk>/cancelar/`) | ver decorator da action | `POST` | jeton alvo | validações de cancelamento | service de status | cancela jeton | gerência de jeton | `messages` success/error |
| `add_auxilio_action` | `verbas_indenizatorias/views/auxilios/actions.py` | `add_auxilio_action` (`/verbas/auxilios/novo/action/`) | ver decorator da action | `POST` | dados de auxílio | validações de elegibilidade | services/helpers de auxílios | cria auxílio | listas/gerência de auxílios | `messages` success/error |
| `solicitar_autorizacao_auxilio_action` | `verbas_indenizatorias/views/auxilios/actions.py` | `solicitar_autorizacao_auxilio_action` (`/verbas/auxilios/<int:pk>/solicitar-autorizacao/`) | ver decorator da action | `POST` | auxílio alvo | validações de elegibilidade | service de status | solicita autorização de auxílio | gerência de auxílio | `messages` success/error |
| `autorizar_auxilio_action` | `verbas_indenizatorias/views/auxilios/actions.py` | `autorizar_auxilio_action` (`/verbas/auxilios/<int:pk>/autorizar/`) | ver decorator da action | `POST` | auxílio alvo | validações de autorização | service de status | autoriza auxílio | gerência de auxílio | `messages` success/error |
| `cancelar_auxilio_action` | `verbas_indenizatorias/views/auxilios/actions.py` | `cancelar_auxilio_action` (`/verbas/auxilios/<int:pk>/cancelar/`) | ver decorator da action | `POST` | auxílio alvo | validações de cancelamento | service de status | cancela auxílio | gerência de auxílio | `messages` success/error |

## Catálogo de Actions de Suprimentos

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `add_suprimento_action` | `suprimentos/views/cadastro/actions.py` | `add_suprimento_action` (`/suprimentos/novo/action/`) | ver decorator da action | `POST` | dados cadastrais de suprimento | validação de formulário e limites | service de cadastro de suprimento | cria suprimento e processo associado | painel/lista de suprimentos | `messages` success/error |
| `adicionar_despesa_action` | `suprimentos/views/prestacao_contas/actions.py` | `registrar_despesa_action` (`/suprimentos/<int:pk>/despesas/adicionar/`) | ver decorator da action | `POST` | despesa e suprimento alvo | validação de prestação e documentos | service de prestação de contas | registra despesa do suprimento | gerência de suprimento | `messages` success/error |
| `fechar_suprimento_action` | `suprimentos/views/prestacao_contas/actions.py` | `concluir_prestacao_action` (`/suprimentos/<int:pk>/fechar/`) | ver decorator da action | `POST` | suprimento alvo | validação de fechamento e pendências | service de prestação de contas | conclui prestação do suprimento | gerência/painel de suprimentos | `messages` success/error |

## Dicionário de Workers/Helpers Fiscais

### anexar_guia_comprovante_relatorio_em_processos

| Campo | Valor |
|---|---|
| Worker | `anexar_guia_comprovante_relatorio_em_processos` |
| Arquivo | `fiscal/services/impostos.py` |
| Assinatura | `(retencoes, guia_bytes, guia_nome, comprovante_bytes, comprovante_nome, mes, ano) -> int` |
| Pré-condições | retenções com `processo_pagamento` definido e competência válida |
| Mutações | cria anexos de guia, comprovante e relatório por processo de recolhimento |
| Auditoria | rastreabilidade por anexos vinculados ao processo |
| Erros/retorno | retorna `0` quando não há processos elegíveis |
| Atomicidade | `transaction.atomic` |

### gerar_lotes_reinf

| Campo | Valor |
|---|---|
| Worker | `gerar_lotes_reinf` |
| Arquivo | `fiscal/services/reinf.py` |
| Assinatura | `gerar_lotes_reinf(mes, ano) -> dict` |
| Pré-condições | competência válida e retenções elegíveis |
| Mutações | geração de artefatos XML em memória |
| Auditoria | evidência operacional via zip retornado ao usuário |
| Erros/retorno | pode lançar `ValueError` para competência sem dados |
| Atomicidade | não aplica |

## Dicionário de Workers/Helpers do Fluxo

### _salvar_processo_completo

| Campo | Valor |
|---|---|
| Worker | `_salvar_processo_completo` |
| Arquivo | `fluxo/views/pre_payment/helpers.py` |
| Assinatura | `(processo_form, mutator_func=None, **formsets) -> Processo` |
| Pré-condições | formulário principal válido e formsets consistentes |
| Mutações | salva processo e formsets associados |
| Auditoria | histórico do modelo e trilhas de alteração por objeto |
| Erros/retorno | propaga exceções de validação/persistência |
| Atomicidade | `transaction.atomic` |

### _registrar_empenho_e_anexar_siscac

| Campo | Valor |
|---|---|
| Worker | `_registrar_empenho_e_anexar_siscac` |
| Arquivo | `fluxo/views/pre_payment/helpers.py` |
| Assinatura | `(processo, n_empenho, data_empenho_str, siscac_file, ano_exercicio=None) -> None` |
| Pré-condições | número/data de empenho válidos |
| Mutações | registra dados orçamentários e anexa SISCAC como documento orçamentário |
| Auditoria | histórico de atualização do processo e documentos |
| Erros/retorno | pode lançar erro de parsing/validação |
| Atomicidade | acionado dentro de transação na action |

### _processar_acao_lote

| Campo | Valor |
|---|---|
| Worker | `_processar_acao_lote` |
| Arquivo | `fluxo/views/helpers/payment_builders.py` |
| Assinatura | `(request, *, param_name, status_origem_esperado, status_destino, ..., redirect_to) -> HttpResponse` |
| Pré-condições | seleção de IDs via POST e status de origem elegível |
| Mutações | transições de status em lote via `_atualizar_status_em_lote` |
| Auditoria | usa `avancar_status(..., usuario=...)` preservando rastreio |
| Erros/retorno | retorna redirect com mensagens para vazio/ignorados/erro |
| Atomicidade | `_atualizar_status_em_lote` usa `transaction.atomic` |

### _iniciar_fila_sessao

| Campo | Valor |
|---|---|
| Worker | `_iniciar_fila_sessao` |
| Arquivo | `fluxo/views/helpers/workflows.py` |
| Assinatura | `(request, queue_key, fallback_view, detail_view, extra_args=None) -> HttpResponse` |
| Pré-condições | requisição `POST` com IDs de processo |
| Mutações | grava fila de revisão em sessão do usuário |
| Auditoria | não altera domínio; altera sessão de navegação |
| Erros/retorno | redirect para fallback quando sem seleção ou método inválido |
| Atomicidade | não aplica |

### _aprovar_processo_view

| Campo | Valor |
|---|---|
| Worker | `_aprovar_processo_view` |
| Arquivo | `fluxo/views/helpers/workflows.py` |
| Assinatura | `(request, pk, *, permission, new_status, success_message, redirect_to) -> HttpResponse` |
| Pré-condições | usuário com permissão e processo existente |
| Mutações | avança status do processo para etapa de destino |
| Auditoria | transição registrada por `avancar_status` com usuário |
| Erros/retorno | redirect final para painel da etapa |
| Atomicidade | encapsulada no método de domínio |

### _recusar_processo_view

| Campo | Valor |
|---|---|
| Worker | `_recusar_processo_view` |
| Arquivo | `fluxo/views/helpers/workflows.py` |
| Assinatura | `(request, pk, *, permission, status_devolucao, error_message, redirect_to) -> HttpResponse` |
| Pré-condições | permissão válida e pendência de recusa válida |
| Mutações | cria pendência e devolve processo ao status anterior definido |
| Auditoria | pendência e transição registradas no histórico |
| Erros/retorno | mensagens de warning para formulário inválido |
| Atomicidade | `_registrar_recusa` usa `transaction.atomic` |

### _executar_arquivamento_definitivo

| Campo | Valor |
|---|---|
| Worker | `_executar_arquivamento_definitivo` |
| Arquivo | `fluxo/views/helpers/archival.py` |
| Assinatura | `(processo, usuario) -> bool` |
| Pré-condições | processo com documentos válidos para consolidar |
| Mutações | gera PDF final, salva `arquivo_final` e avança para `ARQUIVADO` |
| Auditoria | transição final auditável e artefato consolidado anexado |
| Erros/retorno | lança `ArquivamentoSemDocumentosError` e `ArquivamentoDefinitivoError` |
| Atomicidade | `transaction.atomic` |

### aplicar_aprovacao_contingencia

| Campo | Valor |
|---|---|
| Worker | `aplicar_aprovacao_contingencia` |
| Arquivo | `fluxo/views/helpers/contingencias.py` |
| Assinatura | `(contingencia) -> tuple[bool, str|None]` |
| Pré-condições | contingência aprovada em etapa válida e dados normalizados |
| Mutações | aplica alterações ao processo e encerra contingência |
| Auditoria | atualização de processo + status da contingência |
| Erros/retorno | retorna `(False, mensagem)` quando houver inconsistência |
| Atomicidade | `transaction.atomic` |

## Dicionário de Workers/Helpers de Verbas Indenizatórias

### criar_processo_e_vincular_verbas

| Campo | Valor |
|---|---|
| Worker | `criar_processo_e_vincular_verbas` |
| Arquivo | `verbas_indenizatorias/services/processo_integration.py` |
| Assinatura | `(itens, tipo_verba, credor_obj, usuario=None) -> tuple[Processo, list]` |
| Pré-condições | itens aprovados, sem processo e credor resolvido |
| Mutações | cria processo de pagamento e vincula verbas selecionadas |
| Auditoria | transições das verbas e criação de assinatura/PCD quando aplicável |
| Erros/retorno | retorna lista de falhas de PCD para tratamento na view |
| Atomicidade | `transaction.atomic` |

### _forcar_campos_canonicos_processo_verbas

| Campo | Valor |
|---|---|
| Worker | `_forcar_campos_canonicos_processo_verbas` |
| Arquivo | `verbas_indenizatorias/views/processo/helpers.py` |
| Assinatura | `(processo) -> dict` |
| Pré-condições | processo de verbas existente |
| Mutações | ajusta tipo de pagamento, extraorçamentário e totais do processo |
| Auditoria | atualizações rastreadas no histórico do processo |
| Erros/retorno | retorna totais consolidados para a camada de view |
| Atomicidade | não explícita; executa updates pontuais |

### _salvar_documento_upload

| Campo | Valor |
|---|---|
| Worker | `_salvar_documento_upload` |
| Arquivo | `verbas_indenizatorias/views/shared/documents.py` |
| Assinatura | `(entidade, modelo_documento, fk_name, arquivo, tipo_id, obrigatorio=False) -> tuple[object|None, str|None]` |
| Pré-condições | arquivo enviado e tipo de documento válido |
| Mutações | cria documento vinculado à verba alvo |
| Auditoria | anexo documental associado à entidade de verba |
| Erros/retorno | retorna mensagem de erro funcional para a action |
| Atomicidade | depende da operação de criação de documento |

## Dicionário de Workers/Helpers de Suprimentos

### criar_processo_para_suprimento

| Campo | Valor |
|---|---|
| Worker | `criar_processo_para_suprimento` |
| Arquivo | `suprimentos/services/processo_integration.py` |
| Assinatura | `(suprimento, detalhamento) -> Processo` |
| Pré-condições | suprimento válido e dados de credor disponíveis |
| Mutações | cria processo financeiro e vincula ao suprimento |
| Auditoria | histórico de criação/vinculação no domínio de processo |
| Erros/retorno | propaga exceções de persistência |
| Atomicidade | `transaction.atomic` |

### _persistir_suprimento_com_processo

| Campo | Valor |
|---|---|
| Worker | `_persistir_suprimento_com_processo` |
| Arquivo | `suprimentos/views/cadastro/actions.py` |
| Assinatura | `(form_suprimento) -> SuprimentoDeFundos` |
| Pré-condições | formulário válido |
| Mutações | cria suprimento em status aberto e dispara criação do processo vinculado |
| Auditoria | criação registrada em suprimento e processo |
| Erros/retorno | propaga `ValidationError`/`DatabaseError` |
| Atomicidade | `transaction.atomic` |

### _atualizar_status_apos_fechamento

| Campo | Valor |
|---|---|
| Worker | `_atualizar_status_apos_fechamento` |
| Arquivo | `suprimentos/views/helpers.py` |
| Assinatura | `(suprimento) -> None` |
| Pré-condições | suprimento não encerrado |
| Mutações | atualiza status do processo para conferência e encerra suprimento |
| Auditoria | transição de status do processo e do suprimento |
| Erros/retorno | propaga erros de persistência/transição |
| Atomicidade | `transaction.atomic` |
