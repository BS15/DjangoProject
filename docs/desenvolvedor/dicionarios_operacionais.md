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
| Validações | exige competência no formato AAAA-MM; mês deve estar em 1-12; retorna HTTP 400 com mensagem descritiva quando ausente ou inválida |
| Worker | `fiscal.services.gerar_lotes_reinf` |
| Efeitos | gera XMLs de lotes EFD-Reinf e devolve zip em resposta HTTP |
| Redirect | não aplica (retorna arquivo) |
| Feedback | HTTP 400 com mensagem de erro quando competência inválida; HTTP 404 quando não há lotes elegíveis para a competência informada |

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
| Worker | sem worker dedicado (integração externa ainda não habilitada) |
| Efeitos | sem mutação de dados |
| Redirect | `painel_reinf_view` |
| Feedback | warning de funcionalidade indisponível |

## Catálogo de Actions de Pagamentos

### Namespace `pre_payment`

#### Etapa `cadastro`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `add_process_action` | `pagamentos/views/pre_payment/cadastro/actions.py` | `add_process_action` (`/adicionar/action/`) | `fluxo.acesso_backoffice` | `POST` | dados de capa e formsets iniciais | regras de criação e consistência de processo | `_salvar_processo_completo` (orquestração) | cria processo e registros associados | `editar_processo` | `messages` success/error |
| `editar_processo_capa_action` | `pagamentos/views/pre_payment/cadastro/actions.py` | `editar_processo_capa_action` (`/processo/<int:pk>/editar/capa/action/`) | `fluxo.acesso_backoffice` | `POST` | dados de capa do processo | validação de formulário e status elegível | `_salvar_processo_completo` (orquestração) | atualiza dados de capa | tela de edição do processo | `messages` success/error |
| `editar_processo_documentos_action` | `pagamentos/views/pre_payment/cadastro/actions.py` | `editar_processo_documentos_action` (`/processo/<int:pk>/editar/documentos/action/`) | `fluxo.acesso_backoffice` | `POST` | payload documental e anexos | regras documentais e de etapa | `_salvar_formsets_em_transacao` (orquestração) | cria/atualiza documentos e pendências | tela de edição do processo | `messages` success/error |
| `editar_processo_pendencias_action` | `pagamentos/views/pre_payment/cadastro/actions.py` | `editar_processo_pendencias_action` (`/processo/<int:pk>/editar/pendencias/action/`) | `fluxo.acesso_backoffice` | `POST` | atualização de pendências | validação de estado de pendências | `_atualizar_status_pendencia` (orquestração) | altera status de pendências | tela de edição do processo | `messages` success/error |

#### Etapa `empenho`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `registrar_empenho_action` | `pagamentos/views/pre_payment/empenho/actions.py` | `registrar_empenho_action` (`/a-empenhar/registrar-empenho/`) | `fluxo.pode_operar_contas_pagar` | `POST` | dados de empenho e processo alvo | consistência de valores e elegibilidade | `_registrar_empenho_e_anexar_siscac` | registra dados de empenho no processo | painel/fluxo de empenho | `messages` success/error |

#### Etapa `liquidacoes`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `alternar_ateste_nota_action` | `pagamentos/views/pre_payment/liquidacoes/actions.py` | `alternar_ateste_nota` (`/liquidacoes/atestar/<int:pk>/`) | `fluxo.pode_atestar_liquidacao` | `POST` | identificação da nota | valida elegibilidade de ateste | sem worker dedicado (mutação local na action) | alterna estado de ateste | painel de liquidações | `messages` success/error |
| `avancar_para_pagamento_action` | `pagamentos/views/pre_payment/liquidacoes/actions.py` | `avancar_para_pagamento` (`/processo/<int:pk>/avancar-para-pagamento/`) | `fluxo.pode_operar_contas_pagar` | `POST` | processo alvo | turnpikes de liquidação e obrigatoriedades | `processo.avancar_status(...)` (método de domínio) | avança processo para pagamento | hub do processo/painel | `messages` success/error |

### Namespace `payment`

#### Etapa `contas_a_pagar`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `enviar_para_autorizacao_action` | `pagamentos/views/payment/contas_a_pagar/actions.py` | `enviar_para_autorizacao` (`/processos/enviar-autorizacao/`) | `fluxo.pode_operar_contas_pagar` | `POST` | seleção de processos | validação de elegibilidade para autorização | `_processar_acao_lote` | altera estado para autorização | painel de contas a pagar | `messages` success/error |

#### Etapa `autorizacao`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `autorizar_pagamento` | `pagamentos/views/payment/autorizacao/actions.py` | `autorizar_pagamento` (`/processos/autorizar-pagamento/`) | `fluxo.pode_autorizar_pagamento` | `POST` | seleção de processos para autorização | valida permissão e critérios de autorização | `_processar_acao_lote` | autoriza pagamento de processos | painel de autorização | `messages` success/error |
| `recusar_autorizacao_action` | `pagamentos/views/payment/autorizacao/actions.py` | `recusar_autorizacao` (`/processos/autorizacao/<int:pk>/recusar/`) | `fluxo.pode_autorizar_pagamento` | `POST` | processo e motivo de recusa | validação de estado e permissão | `_recusar_processo_view` | registra recusa e atualiza estado | painel de autorização | `messages` success/error |

#### Etapa `lancamento`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `separar_para_lancamento_bancario_action` | `pagamentos/views/payment/lancamento/actions.py` | `separar_para_lancamento_bancario` (`/processos/separar-lancamento/`) | `fluxo.pode_operar_contas_pagar` | `POST` | seleção de processos | validação de status elegível para lançamento | sem worker dedicado (orquestração em sessão) | separa processos para lançamento | painel de lançamento bancário | `messages` success/error |
| `marcar_como_lancado_action` | `pagamentos/views/payment/lancamento/actions.py` | `marcar_como_lancado` (`/processos/marcar-lancado/`) | `fluxo.pode_operar_contas_pagar` | `POST` | seleção de processos lançados | validação de lote e estado | `_processar_acao_lote` | marca processos como lançados | painel de lançamento bancário | `messages` success/error |
| `desmarcar_lancamento_action` | `pagamentos/views/payment/lancamento/actions.py` | `desmarcar_lancamento` (`/processos/desmarcar-lancamento/`) | `fluxo.pode_operar_contas_pagar` | `POST` | seleção de processos | validação de reversão permitida | `_processar_acao_lote` | reverte marcação de lançamento | painel de lançamento bancário | `messages` success/error |

### Namespace `post_payment`

#### Etapa `conferencia`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `iniciar_conferencia_action` | `pagamentos/views/post_payment/conferencia/actions.py` | `iniciar_conferencia` (`/processos/conferencia/iniciar/`) | `fluxo.pode_operar_contas_pagar` | `POST` | seleção de processos | valida elegibilidade para conferência | `_iniciar_fila_sessao` | move processos para revisão de conferência | painel de conferência | `messages` success/error |
| `aprovar_conferencia_action` | `pagamentos/views/post_payment/conferencia/actions.py` | `aprovar_conferencia` (`/processos/conferencia/<int:pk>/aprovar/`) | `fluxo.pode_operar_contas_pagar` | `POST` | processo alvo | valida checklist da etapa | sem worker dedicado (ação atualmente sem mutação) | aprova conferência e avança fluxo | painel de conferência | `messages` success/error |

#### Etapa `contabilizacao`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `iniciar_contabilizacao_action` | `pagamentos/views/post_payment/contabilizacao/actions.py` | `iniciar_contabilizacao` (`/processos/contabilizacao/iniciar/`) | `fluxo.pode_contabilizar` | `POST` | seleção de processos | valida elegibilidade para contabilização | `_iniciar_fila_sessao` | inicia etapa de contabilização | painel de contabilização | `messages` success/error |
| `aprovar_contabilizacao_action` | `pagamentos/views/post_payment/contabilizacao/actions.py` | `aprovar_contabilizacao` (`/processos/contabilizacao/<int:pk>/aprovar/`) | `fluxo.pode_contabilizar` | `POST` | processo alvo | valida regras da etapa | `_aprovar_processo_view` | aprova contabilização | painel de contabilização | `messages` success/error |
| `recusar_contabilizacao_action` | `pagamentos/views/post_payment/contabilizacao/actions.py` | `recusar_contabilizacao` (`/processos/contabilizacao/<int:pk>/recusar/`) | `fluxo.pode_contabilizar` | `POST` | processo e justificativa | valida recusa permitida | `_recusar_processo_view` | recusa contabilização e ajusta estado | painel de contabilização | `messages` success/error |

#### Etapa `conselho`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `aprovar_conselho_action` | `pagamentos/views/post_payment/conselho/actions.py` | `aprovar_conselho` (`/processos/conselho/<int:pk>/aprovar/`) | `fluxo.pode_auditar_conselho` | `POST` | processo em análise de conselho | validações de deliberação | `_aprovar_processo_view` | aprova deliberação | painel de conselho | `messages` success/error |
| `recusar_conselho_action` | `pagamentos/views/post_payment/conselho/actions.py` | `recusar_conselho` (`/processos/conselho/<int:pk>/recusar/`) | `fluxo.pode_auditar_conselho` | `POST` | processo e justificativa | validações de recusa | `_recusar_processo_view` | recusa deliberação | painel de conselho | `messages` success/error |

#### Etapa `reunioes`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `gerenciar_reunioes_action` | `pagamentos/views/post_payment/reunioes/actions.py` | `gerenciar_reunioes_action` (`/processos/conselho/reunioes/criar/`) | `fluxo.pode_auditar_conselho` | `POST` | dados da reunião | validações de criação de reunião | sem worker dedicado (orquestração na própria action) | cria/atualiza reunião | painel de reuniões | `messages` success/error |
| `montar_pauta_reuniao_action` | `pagamentos/views/post_payment/reunioes/actions.py` | `montar_pauta_reuniao_action` (`/processos/conselho/reunioes/<int:reuniao_id>/montar-pauta/adicionar/`) | `fluxo.pode_auditar_conselho` | `POST` | itens da pauta e reunião alvo | validações de elegibilidade dos processos | sem worker dedicado (orquestração na própria action) | vincula itens na pauta | tela de pauta da reunião | `messages` success/error |
| `iniciar_conselho_reuniao_action` | `pagamentos/views/post_payment/reunioes/actions.py` | `iniciar_conselho_reuniao` (`/processos/conselho/reunioes/<int:reuniao_id>/iniciar/`) | `fluxo.pode_auditar_conselho` | `POST` | reunião alvo | validações de prontidão da pauta | sem worker dedicado (orquestração na própria action) | inicia sessão de conselho | análise de reunião/painel | `messages` success/error |

#### Etapa `arquivamento`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `arquivar_processo_action` | `pagamentos/views/post_payment/arquivamento/actions.py` | `arquivar_processo_action` (`/processos/arquivamento/<int:pk>/executar/`) | `fluxo.pode_arquivar` | `POST` | processo alvo | validações de encerramento e completude | `_executar_arquivamento_definitivo` | arquiva processo | painel de arquivamento | `messages` success/error |

### Namespace `support`

#### Etapa `pendencia`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `atualizar_pendencias_lote_action` | `pagamentos/views/support/pendencia/actions.py` | `painel_pendencias_action` (`/pendencias/action/`) | `fluxo.acesso_backoffice` | `POST` | lote de pendências e status | validação de lote e transições permitidas | sem worker dedicado (mutação local na action) | atualiza múltiplas pendências | painel de pendências | `messages` success/error |

#### Etapa `devolucao`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `registrar_devolucao_action` | `pagamentos/views/support/devolucao/actions.py` | `registrar_devolucao_action` (`/processo/<int:processo_id>/devolucao/salvar/`) | `fluxo.acesso_backoffice` | `POST` | dados da devolução e processo | validações de devolução e anexos | sem worker dedicado (`form.save()` na action) | registra devolução financeira/documental | painel de devoluções/processo | `messages` success/error |

#### Etapa `contingencia`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `add_contingencia_action` | `pagamentos/views/support/contingencia/actions.py` | `add_contingencia_action` (`/contingencias/nova/enviar/`) | `fluxo.acesso_backoffice` | `POST` | dados de contingência | validação de elegibilidade e campos obrigatórios | `normalizar_dados_propostos_contingencia` + `determinar_requisitos_contingencia` | cria contingência vinculada ao processo | painel de contingências | `messages` success/error |
| `analisar_contingencia_action` | `pagamentos/views/support/contingencia/actions.py` | `analisar_contingencia` (`/contingencias/<int:pk>/analisar/`) | `fluxo.acesso_backoffice` | `POST` | decisão sobre contingência | validação de estado e permissão | `processar_aprovacao_contingencia` + `processar_revisao_contadora_contingencia` | aprova/recusa contingência e atualiza estado | painel de contingências | `messages` success/error |

#### Etapa `contas_fixas`

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `add_conta_fixa_action` | `pagamentos/views/support/contas_fixas/actions.py` | `add_conta_fixa_action` (`/contas-fixas/nova/action/`) | não implementado no codebase (`actions.py/` vazio) | `POST` | dados da conta fixa | validação de formulário | não implementado no codebase (`actions.py/` vazio) | cria conta/fatura | painel de contas fixas | `messages` success/error |
| `edit_conta_fixa_action` | `pagamentos/views/support/contas_fixas/actions.py` | `edit_conta_fixa_action` (`/contas-fixas/<int:pk>/editar/action/`) | não implementado no codebase (`actions.py/` vazio) | `POST` | atualização de conta fixa | validação de formulário | não implementado no codebase (`actions.py/` vazio) | atualiza conta/fatura | painel de contas fixas | `messages` success/error |
| `vincular_processo_fatura_action` | `pagamentos/views/support/contas_fixas/actions.py` | `vincular_processo_fatura` (`/contas-fixas/<int:fatura_id>/vincular/`) | não implementado no codebase (`actions.py/` vazio) | `POST` | fatura e processo alvo | validação de vínculo permitido | não implementado no codebase (`actions.py/` vazio) | vincula fatura a processo | painel de contas fixas | `messages` success/error |
| `excluir_conta_fixa_action` | `pagamentos/views/support/contas_fixas/actions.py` | `excluir_conta_fixa` (`/contas-fixas/<int:pk>/excluir/`) | não implementado no codebase (`actions.py/` vazio) | `POST` | conta fixa alvo | validação de exclusão permitida | não implementado no codebase (`actions.py/` vazio) | remove/desativa vínculo conforme regra do módulo | painel de contas fixas | `messages` success/error |

## Catálogo de Actions de Verbas Indenizatórias

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `editar_processo_verbas_capa_action` | `verbas_indenizatorias/views/processo/actions.py` | `editar_processo_verbas_capa_action` (`/processo/<int:pk>/editar-verbas/capa/action/`) | `verbas_indenizatorias.pode_gerenciar_processos_verbas` | `POST` | dados de capa do processo de verbas | validação de formulário | `_forcar_campos_canonicos_processo_verbas` + `ProcessoForm.save()` | atualiza capa do processo | tela de edição de verbas | `messages` success/error |
| `editar_processo_verbas_pendencias_action` | `verbas_indenizatorias/views/processo/actions.py` | `editar_processo_verbas_pendencias_action` (`/processo/<int:pk>/editar-verbas/pendencias/action/`) | `verbas_indenizatorias.pode_gerenciar_processos_verbas` | `POST` | atualização de pendências | validação de transições de pendência | `PendenciaFormSet.save()` + `_forcar_campos_canonicos_processo_verbas` | atualiza pendências | tela de edição de verbas | `messages` success/error |
| `editar_processo_verbas_documentos_action` | `verbas_indenizatorias/views/processo/actions.py` | `editar_processo_verbas_documentos_action` (`/processo/<int:pk>/editar-verbas/documentos/action/`) | `verbas_indenizatorias.pode_gerenciar_processos_verbas` | `POST` | dados documentais e anexos | regras documentais da etapa | `DocumentoFormSet.save()` | cria/atualiza documentos | tela de edição de verbas | `messages` success/error |
| `agrupar_verbas_view` | `verbas_indenizatorias/views/processo/actions.py` | `agrupar_verbas` (`/verbas/agrupar/<str:tipo_verba>/`) | `verbas_indenizatorias.pode_agrupar_verbas` | `POST` | tipo de verba + seleção de itens | validação por tipo de verba | `criar_processo_e_vincular_verbas` | agrupa verbas em processo de pagamento | painel de verbas | `messages` success/error |
| `add_diaria_action` | `verbas_indenizatorias/views/diarias/actions.py` | `add_diaria_action` (`/verbas/diarias/nova/action/`) | `verbas_indenizatorias.pode_criar_diarias` | `POST` | dados de diária | validações de beneficiário e período | `_salvar_diaria_base` | cria diária e estado inicial | listas/gerência de diárias | `messages` success/error |
| `registrar_comprovante_action` | `verbas_indenizatorias/views/diarias/actions.py` | `registrar_comprovante_action` (`/verbas/diarias/<int:pk>/comprovantes/registrar/`) | `verbas_indenizatorias.pode_gerenciar_diarias` | `POST` | comprovante e diária alvo | validação de arquivo e estado | `_salvar_documento_upload` | anexa comprovante e ajusta estado | gerência da diária | `messages` success/error |
| `cancelar_diaria_action` | `verbas_indenizatorias/views/diarias/actions.py` | `cancelar_diaria_action` (`/verbas/diarias/<int:pk>/cancelar/`) | `verbas_indenizatorias.pode_gerenciar_diarias` | `POST` | diária alvo | validação de cancelamento permitido | `diaria.avancar_status(...)` + `_set_status_case_insensitive` | cancela diária | listas/gerência de diárias | `messages` success/error |
| `add_reembolso_action` | `verbas_indenizatorias/views/reembolsos/actions.py` | `add_reembolso_action` (`/verbas/reembolsos/novo/action/`) | `verbas_indenizatorias.pode_gerenciar_reembolsos` | `POST` | dados de reembolso | validações de campos e valores | `ReembolsoForm.save()` | cria reembolso | listas/gerência de reembolsos | `messages` success/error |
| `solicitar_autorizacao_reembolso_action` | `verbas_indenizatorias/views/reembolsos/actions.py` | `solicitar_autorizacao_reembolso_action` (`/verbas/reembolsos/<int:pk>/solicitar-autorizacao/`) | `verbas_indenizatorias.pode_gerenciar_reembolsos` | `POST` | reembolso alvo | validações de elegibilidade | `_set_status_case_insensitive` | altera status para solicitação de autorização | gerência de reembolso | `messages` success/error |
| `autorizar_reembolso_action` | `verbas_indenizatorias/views/reembolsos/actions.py` | `autorizar_reembolso_action` (`/verbas/reembolsos/<int:pk>/autorizar/`) | `verbas_indenizatorias.pode_gerenciar_reembolsos` | `POST` | reembolso alvo | validações de autorização | `_set_status_case_insensitive` | autoriza reembolso | gerência de reembolso | `messages` success/error |
| `cancelar_reembolso_action` | `verbas_indenizatorias/views/reembolsos/actions.py` | `cancelar_reembolso_action` (`/verbas/reembolsos/<int:pk>/cancelar/`) | `verbas_indenizatorias.pode_gerenciar_reembolsos` | `POST` | reembolso alvo | validações de cancelamento | `_set_status_case_insensitive` | cancela reembolso | gerência de reembolso | `messages` success/error |
| `registrar_comprovante_reembolso_action` | `verbas_indenizatorias/views/reembolsos/actions.py` | `registrar_comprovante_reembolso_action` (`/verbas/reembolsos/<int:pk>/comprovantes/registrar/`) | `verbas_indenizatorias.pode_gerenciar_reembolsos` | `POST` | comprovante e reembolso alvo | validação de arquivo e elegibilidade | `_salvar_documento_upload` | anexa comprovante | gerência de reembolso | `messages` success/error |
| `add_jeton_action` | `verbas_indenizatorias/views/jetons/actions.py` | `add_jeton_action` (`/verbas/jetons/novo/action/`) | `verbas_indenizatorias.pode_gerenciar_jetons` | `POST` | dados de jeton | validações de sessão/beneficiário | `JetonForm.save()` | cria jeton | listas/gerência de jetons | `messages` success/error |
| `solicitar_autorizacao_jeton_action` | `verbas_indenizatorias/views/jetons/actions.py` | `solicitar_autorizacao_jeton_action` (`/verbas/jetons/<int:pk>/solicitar-autorizacao/`) | `verbas_indenizatorias.pode_gerenciar_jetons` | `POST` | jeton alvo | validações de elegibilidade | `_set_status_case_insensitive` | solicita autorização de jeton | gerência de jeton | `messages` success/error |
| `autorizar_jeton_action` | `verbas_indenizatorias/views/jetons/actions.py` | `autorizar_jeton_action` (`/verbas/jetons/<int:pk>/autorizar/`) | `verbas_indenizatorias.pode_gerenciar_jetons` | `POST` | jeton alvo | validações de autorização | `_set_status_case_insensitive` | autoriza jeton | gerência de jeton | `messages` success/error |
| `cancelar_jeton_action` | `verbas_indenizatorias/views/jetons/actions.py` | `cancelar_jeton_action` (`/verbas/jetons/<int:pk>/cancelar/`) | `verbas_indenizatorias.pode_gerenciar_jetons` | `POST` | jeton alvo | validações de cancelamento | `_set_status_case_insensitive` | cancela jeton | gerência de jeton | `messages` success/error |
| `add_auxilio_action` | `verbas_indenizatorias/views/auxilios/actions.py` | `add_auxilio_action` (`/verbas/auxilios/novo/action/`) | `verbas_indenizatorias.pode_gerenciar_auxilios` | `POST` | dados de auxílio | validações de elegibilidade | `AuxilioForm.save()` | cria auxílio | listas/gerência de auxílios | `messages` success/error |
| `solicitar_autorizacao_auxilio_action` | `verbas_indenizatorias/views/auxilios/actions.py` | `solicitar_autorizacao_auxilio_action` (`/verbas/auxilios/<int:pk>/solicitar-autorizacao/`) | `verbas_indenizatorias.pode_gerenciar_auxilios` | `POST` | auxílio alvo | validações de elegibilidade | `_set_status_case_insensitive` | solicita autorização de auxílio | gerência de auxílio | `messages` success/error |
| `autorizar_auxilio_action` | `verbas_indenizatorias/views/auxilios/actions.py` | `autorizar_auxilio_action` (`/verbas/auxilios/<int:pk>/autorizar/`) | `verbas_indenizatorias.pode_gerenciar_auxilios` | `POST` | auxílio alvo | validações de autorização | `_set_status_case_insensitive` | autoriza auxílio | gerência de auxílio | `messages` success/error |
| `cancelar_auxilio_action` | `verbas_indenizatorias/views/auxilios/actions.py` | `cancelar_auxilio_action` (`/verbas/auxilios/<int:pk>/cancelar/`) | `verbas_indenizatorias.pode_gerenciar_auxilios` | `POST` | auxílio alvo | validações de cancelamento | `_set_status_case_insensitive` | cancela auxílio | gerência de auxílio | `messages` success/error |

## Catálogo de Actions de Suprimentos

| Action | Arquivo | Rota | Permissão | Método | Entrada | Validações | Worker | Efeitos | Redirect | Feedback |
|---|---|---|---|---|---|---|---|---|---|---|
| `add_suprimento_action` | `suprimentos/views/cadastro/actions.py` | `add_suprimento_action` (`/suprimentos/novo/action/`) | `suprimentos.acesso_backoffice` | `POST` | dados cadastrais de suprimento | validação de formulário e limites | `_persistir_suprimento_com_processo` | cria suprimento e processo associado | painel/lista de suprimentos | `messages` success/error |
| `adicionar_despesa_action` | `suprimentos/views/prestacao_contas/actions.py` | `registrar_despesa_action` (`/suprimentos/<int:pk>/despesas/adicionar/`) | `suprimentos.acesso_backoffice` | `POST` | despesa e suprimento alvo | validação de prestação e documentos | `DespesaSuprimentoForm.save()` | registra despesa do suprimento | gerência de suprimento | `messages` success/error |
| `fechar_suprimento_action` | `suprimentos/views/prestacao_contas/actions.py` | `concluir_prestacao_action` (`/suprimentos/<int:pk>/fechar/`) | `suprimentos.acesso_backoffice` | `POST` | suprimento alvo | validação de fechamento e pendências | `_atualizar_status_apos_fechamento` | conclui prestação do suprimento | gerência/painel de suprimentos | `messages` success/error |

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

### Helpers Fiscais de Nota Fiscal (impostos)

### atualizar_retencoes_nota

| Campo | Valor |
|---|---|
| Worker | `atualizar_retencoes_nota` |
| Arquivo | `fiscal/views/impostos/helpers.py` |
| Assinatura | `(nota, retencoes_data) -> None` |
| Pré-condições | nota fiscal e lista de retenções válida |
| Mutações | deleta retenções existentes da nota e recria com novos dados; salva nota com `update_fields` |
| Auditoria | histórico de retenções e da nota fiscal |
| Erros/retorno | propaga `ValidationError` e `DatabaseError` |
| Atomicidade | `transaction.atomic` |

### criar_documento_fiscal

| Campo | Valor |
|---|---|
| Worker | `criar_documento_fiscal` |
| Arquivo | `fiscal/views/impostos/helpers.py` |
| Assinatura | `(processo, dados) -> DocumentoFiscal` |
| Pré-condições | processo existente e dados documentais válidos |
| Mutações | cria `DocumentoFiscal` vinculado ao processo fiscal |
| Auditoria | histórico de criação do `DocumentoFiscal` |
| Erros/retorno | propaga `ValidationError` e `DatabaseError` |
| Atomicidade | `transaction.atomic` |

## Dicionário de Workers/Helpers de Pagamentos

### Helpers de Cadastro de Processos (pre_payment)

### salvar_retencoes_nota_fiscal

| Campo | Valor |
|---|---|
| Worker | `salvar_retencoes_nota_fiscal` |
| Arquivo | `pagamentos/views/pre_payment/cadastro/helpers.py` |
| Assinatura | `(nota, retencoes_data, processo) -> None` |
| Pré-condições | nota fiscal e processo existentes; `retencoes_data` lista válida |
| Mutações | deleta retenções antigas e recria a partir de `retencoes_data`; salva nota com `update_fields` |
| Auditoria | histórico do modelo nota e das retenções vinculadas |
| Erros/retorno | propaga `ValidationError` e `DatabaseError` |
| Atomicidade | `transaction.atomic` |

### criar_nota_fiscal

| Campo | Valor |
|---|---|
| Worker | `criar_nota_fiscal` |
| Arquivo | `pagamentos/views/pre_payment/cadastro/helpers.py` |
| Assinatura | `(processo, dados) -> DocumentoFiscal` |
| Pré-condições | processo existente e dados de nota validados |
| Mutações | cria `DocumentoFiscal` vinculado ao processo |
| Auditoria | histórico de criação do `DocumentoFiscal` |
| Erros/retorno | propaga `ValidationError` e `DatabaseError` |
| Atomicidade | `transaction.atomic` |

### sincronizar_pendencia_nota

| Campo | Valor |
|---|---|
| Worker | `sincronizar_pendencia_nota` |
| Arquivo | `pagamentos/views/pre_payment/cadastro/helpers.py` |
| Assinatura | `(processo, tipo_pendencia, nota) -> None` |
| Pré-condições | processo existente e `tipo_pendencia` definido |
| Mutações | cria ou remove pendências conforme estado da nota |
| Auditoria | pendências vinculadas ao processo com rastreio temporal |
| Erros/retorno | propaga `DatabaseError` |
| Atomicidade | `transaction.atomic` (parte do contexto da action chamadora) |

### Helpers de Comprovantes de Pagamento

### processar_e_salvar_comprovantes

| Campo | Valor |
|---|---|
| Worker | `processar_e_salvar_comprovantes` |
| Arquivo | `pagamentos/views/payment/comprovantes/helpers.py` |
| Assinatura | `(processo, paginas_processadas, usuario) -> None` |
| Pré-condições | processo elegível para registro de comprovante e páginas geradas |
| Mutações | cria `ComprovanteDePagamento` e `DocumentoProcesso`; chama `processo.avancar_status`; salva retenções com `update_fields`; remove arquivo temporário de storage |
| Auditoria | transição de status rastreada em `avancar_status(usuario=...)` |
| Erros/retorno | propaga `ValidationError`; `storage.delete` falha com log |
| Atomicidade | `transaction.atomic` |

### _salvar_processo_completo

| Campo | Valor |
|---|---|
| Worker | `_salvar_processo_completo` |
| Arquivo | `pagamentos/views/pre_payment/helpers.py` |
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
| Arquivo | `pagamentos/views/pre_payment/helpers.py` |
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
| Arquivo | `pagamentos/views/helpers/payment_builders.py` |
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
| Arquivo | `pagamentos/views/helpers/workflows.py` |
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
| Arquivo | `pagamentos/views/helpers/workflows.py` |
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
| Arquivo | `pagamentos/views/helpers/workflows.py` |
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
| Arquivo | `pagamentos/views/helpers/archival.py` |
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
| Arquivo | `pagamentos/views/helpers/contingencias.py` |
| Assinatura | `(contingencia) -> tuple[bool, str|None]` |
| Pré-condições | contingência aprovada em etapa válida e dados normalizados |
| Mutações | aplica alterações ao processo e encerra contingência |
| Auditoria | atualização de processo + status da contingência |
| Erros/retorno | retorna `(False, mensagem)` quando houver inconsistência |
| Atomicidade | `transaction.atomic` |

### Helpers de Contingências

### processar_aprovacao_contingencia

| Campo | Valor |
|---|---|
| Worker | `processar_aprovacao_contingencia` |
| Arquivo | `pagamentos/views/helpers/contingencias.py` |
| Assinatura | `(contingencia, usuario, parecer) -> tuple[bool, str|None]` |
| Pré-condições | contingência em status `PENDENTE_SUPERVISOR`, `PENDENTE_ORDENADOR` ou `PENDENTE_CONSELHO` |
| Mutações | atribui campos de aprovação por etapa; chama `aplicar_aprovacao_contingencia` quando etapa final; chama `sincronizar_flag_contingencia_processo` |
| Auditoria | campos de aprovador e data rastreados; histórico do processo |
| Erros/retorno | retorna `(False, mensagem)` para etapa inválida ou quando `aplicar_aprovacao` falha; retorna `(True, None)` no sucesso |
| Atomicidade | `transaction.atomic` |

### processar_revisao_contadora_contingencia

| Campo | Valor |
|---|---|
| Worker | `processar_revisao_contadora_contingencia` |
| Arquivo | `pagamentos/views/helpers/contingencias.py` |
| Assinatura | `(contingencia, usuario, parecer) -> tuple[bool, str|None]` |
| Pré-condições | contingência em status `PENDENTE_CONTADOR`; parecer não vazio |
| Mutações | atribui `parecer_contadora`, `revisado_por_contadora` e `data_revisao_contadora`; chama `save(update_fields)`; chama `aplicar_aprovacao_contingencia` |
| Auditoria | campos de revisão rastreados; histórico do processo |
| Erros/retorno | retorna `(False, "parecer obrigatório")` se parecer vazio; retorna `(False, msg)` se `aplicar_aprovacao` falha; retorna `(True, None)` no sucesso |
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
| Arquivo | `suprimentos/views/cadastro/helpers.py` |
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
