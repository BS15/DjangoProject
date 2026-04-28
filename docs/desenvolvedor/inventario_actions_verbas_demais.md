# Inventário de Actions — Verbas / Demais trilhas

Este recorte cobre reembolsos, jetons, auxílios e a revisão operacional de solicitações agrupáveis.

## Visão do recorte

| Namespace | Actions |
|---|---:|
| `verbas/reembolsos` | 5 |
| `verbas/jetons` | 4 |
| `verbas/auxilios` | 4 |
| `verbas/solicitacoes` | 1 |
| **Total** | **14** |

## Namespace `verbas/reembolsos`

```mermaid
flowchart TD
    add_reembolso_action --> ReembolsoForm_save[ReembolsoForm.save]
    solicitar_autorizacao_reembolso_action -. mutacao de status .-> reembolso_solicitado[reembolso.definir_status]
    autorizar_reembolso_action -. mutacao de status .-> reembolso_autorizado[reembolso.definir_status]
    cancelar_reembolso_action --> cancelar_verba
    registrar_comprovante_reembolso_action --> _salvar_documento_upload
```

| Action | Worker/helper/service acionado | Efeito principal |
|---|---|---|
| `add_reembolso_action` | `ReembolsoForm.save()` | cria reembolso |
| `solicitar_autorizacao_reembolso_action` | mutação de status | envia reembolso para autorização |
| `autorizar_reembolso_action` | mutação de status | autoriza reembolso |
| `cancelar_reembolso_action` | `cancelar_verba` | cancela reembolso e processa devolução quando couber |
| `registrar_comprovante_reembolso_action` | `_salvar_documento_upload` | anexa comprovante documental |

## Namespace `verbas/jetons`

```mermaid
flowchart TD
    add_jeton_action --> JetonForm_save[JetonForm.save]
    solicitar_autorizacao_jeton_action -. mutacao de status .-> jeton_solicitado[jeton.definir_status]
    autorizar_jeton_action -. mutacao de status .-> jeton_autorizado[jeton.definir_status]
    cancelar_jeton_action --> cancelar_verba
```

| Action | Worker/helper/service acionado | Efeito principal |
|---|---|---|
| `add_jeton_action` | `JetonForm.save()` | cria jeton |
| `solicitar_autorizacao_jeton_action` | mutação de status | envia jeton para autorização |
| `autorizar_jeton_action` | mutação de status | autoriza jeton |
| `cancelar_jeton_action` | `cancelar_verba` | cancela jeton |

## Namespace `verbas/auxilios`

```mermaid
flowchart TD
    add_auxilio_action --> AuxilioForm_save[AuxilioForm.save]
    solicitar_autorizacao_auxilio_action -. mutacao de status .-> auxilio_solicitado[auxilio.definir_status]
    autorizar_auxilio_action -. mutacao de status .-> auxilio_autorizado[auxilio.definir_status]
    cancelar_auxilio_action --> cancelar_verba
```

| Action | Worker/helper/service acionado | Efeito principal |
|---|---|---|
| `add_auxilio_action` | `AuxilioForm.save()` | cria auxílio |
| `solicitar_autorizacao_auxilio_action` | mutação de status | envia auxílio para autorização |
| `autorizar_auxilio_action` | mutação de status | autoriza auxílio |
| `cancelar_auxilio_action` | `cancelar_verba` | cancela auxílio |

## Namespace `verbas/solicitacoes`

```mermaid
flowchart TD
    aprovar_revisao_solicitacao_action --> _emitir_pcd_e_enviar_para_assinatura_beneficiario
    _emitir_pcd_e_enviar_para_assinatura_beneficiario --> gerar_e_anexar_pcd_diaria
    _emitir_pcd_e_enviar_para_assinatura_beneficiario --> enviar_documento_para_assinatura
    aprovar_revisao_solicitacao_action -. mutacao de status .-> definir_status_revisada[solicitacao.definir_status REVISADA]
```

| Action | Worker/helper/service acionado | Efeito principal |
|---|---|---|
| `aprovar_revisao_solicitacao_action` | `_emitir_pcd_e_enviar_para_assinatura_beneficiario`, `gerar_e_anexar_pcd_diaria`, `enviar_documento_para_assinatura` | revisa a solicitação, emite PCD e, no caso de diária, dispara assinatura eletrônica |

## Leitura prática

- Reembolsos, jetons e auxílios seguem um padrão quase espelhado: criar → solicitar autorização → autorizar → cancelar.
- O diferencial está em `reembolsos`, que também possui spoke documental explícita.
- A revisão de solicitações é o ponto onde verbas conversa com a infraestrutura transversal de assinatura eletrônica.