# Controle de Acesso Contextual

O PaGé utiliza duas camadas complementares de controle de acesso:

1. **[RBAC](/governanca/catalogo_permissoes_grupos.md) declarativo** — `@permission_required` decorando cada view, definindo *o que* um perfil pode fazer.
2. **Acesso contextual** — verificações imperativas dentro da view/helper, definindo *sobre qual registro* o usuário pode agir.

Este documento mapeia todos os pontos de controle contextual que **não são** cobertos pelo decorator, listando o helper responsável, as views onde é aplicado e a lógica de decisão.

---

## 1. Verbas Indenizatórias — Diárias

### 1.1 Prestação de contas da diária

| Aspecto | Detalhe |
|---|---|
| **Helper** | `verbas_indenizatorias/views/diarias/access.py` → `_pode_acessar_prestacao(user, diaria)` |
| **Views protegidas** | `panels.py` (detalhe da prestação) · `actions.py` (submeter comprovante, registrar devolução) |
| **Lógica** | Retorna `True` se `diaria.beneficiario.usuario == request.user` **ou** se o usuário possui um de: `verbas_indenizatorias.operar_prestacao_contas`, `verbas_indenizatorias.visualizar_prestacao_contas`, `verbas_indenizatorias.analisar_prestacao_contas` |
| **Resposta ao negar** | `HttpResponseForbidden` |

O credor-beneficiário acessa *apenas a sua própria* prestação de contas; operadores backoffice enxergam todas.

### 1.2 Autorização da diária pelo proponente

| Aspecto | Detalhe |
|---|---|
| **View** | `verbas_indenizatorias/views/diarias/actions.py` → `autorizar_diaria_action` |
| **Lógica** | `diaria.proponente_id != request.user.id` → bloqueia com mensagem de erro e redirect |
| **Resposta ao negar** | `messages.error` + redirect (sem HTTP 403) |

Somente o próprio proponente registrado na diária pode assinar a autorização. Não há permissão de backoffice que substitua esse vínculo.

### 1.3 Gerenciamento de vínculo diária–processo

| Aspecto | Detalhe |
|---|---|
| **Helper** | `access.py` → `_pode_gerenciar_vinculo_diaria(user)` |
| **Views protegidas** | `actions.py` → `vincular_diaria_action` e `desvincular_diaria_action` |
| **Lógica** | `user.has_perm("pagamentos.operador_contas_a_pagar")` — exclusivo de backoffice, sem acesso para o próprio beneficiário |
| **Resposta ao negar** | `HttpResponseForbidden` |

---

## 2. Verbas Indenizatórias — Processos de Verbas

### 2.1 Edição do processo de verbas (hub e spokes)

| Aspecto | Detalhe |
|---|---|
| **Helper** | `verbas_indenizatorias/views/processo/helpers.py` → `_pode_gerenciar_processo_verbas_da_entidade(user, processo)` |
| **Views protegidas** | `processo/panels.py` (hub, capa, pendências, itens, documentos) · `processo/actions.py` (salvar capa, pendências, documentos) |
| **Lógica** | `operador_contas_a_pagar` → acesso irrestrito. `pode_gerenciar_processos_verbas` → apenas se `user_is_entity_owner(user, processo)` (ver §5). |
| **Resposta ao negar** | `raise PermissionDenied` |

---

## 3. Suprimentos — Prestação de Contas

### 3.1 Acesso ao suprimento pelo suprido

| Aspecto | Detalhe |
|---|---|
| **Helper** | `suprimentos/views/helpers.py` → `_pode_acessar_suprimento(user, suprimento)` |
| **Views protegidas** | `prestacao_contas/panels.py` (painel e detalhe) · `prestacao_contas/actions.py` (lançar despesa, submeter prestação, excluir despesa) |
| **Lógica** | `suprimento.suprido.usuario_id == user.pk`. Backoffice com `suprimentos.pode_gerenciar_concessao_suprimento` tem acesso independentemente. |
| **Resposta ao negar** | `raise PermissionDenied` |

O suprido acessa *apenas o seu próprio* suprimento de fundos; não há visibilidade cruzada entre supridos.

---

## 4. Liquidações — Ateste de Notas Fiscais

### 4.1 Edição de liquidação pelo fiscal de contrato

| Aspecto | Detalhe |
|---|---|
| **View** | `pagamentos/views/pre_payment/liquidacoes/actions.py` → `confirmar_liquidacao_action` |
| **Lógica** | `liquidacao.fiscal_contrato_id != request.user.pk and not user.has_perm("pagamentos.operador_contas_a_pagar")` → bloqueia |
| **Resposta ao negar** | `raise PermissionDenied` |

---

## 5. Assinaturas Eletrônicas

### 5.1 Disparo de assinatura

| Aspecto | Detalhe |
|---|---|
| **View** | `pagamentos/views/support/signatures.py` → `disparar_assinatura_action` |
| **Lógica** | `assinatura.criador != request.user` → PermissionDenied |
| **Resposta ao negar** | `raise PermissionDenied` |

---

## 6. Download Seguro de Arquivos

### 6.1 Roteamento de acesso por tipo de documento

| Aspecto | Detalhe |
|---|---|
| **View** | `pagamentos/views/security/__init__.py` → `download_arquivo_seguro` |
| **Lógica** | Superusuário ou `pagamentos.pode_auditar_conselho` → acesso irrestrito. Para `verba_diaria_comprov` delega a `_pode_acessar_prestacao`. Para demais documentos delega a `user_is_entity_owner` (ver §7). |
| **Efeito colateral** | Toda tentativa de download grava `RegistroAcessoArquivoProcessual` independentemente do resultado. |
| **Resposta ao negar** | `HttpResponseForbidden` |

---

## 7. Ownership Genérico — `user_is_entity_owner`

`commons/shared/access_utils.py` → `user_is_entity_owner(user, entidade)`

Verifica, por ordem de prioridade, se o usuário autenticado está vinculado à entidade por um dos campos abaixo. A comparação usa e-mail normalizado (lowercase, strip) como fallback quando não há FK direta.

| Campo testado | Típico em |
|---|---|
| `proponente` | Diária, Processo de Verbas |
| `beneficiario` | Diária, Jeton, Auxílio, Reembolso |
| `credor` | Processo de Pagamento |
| `suprido` | Suprimento de Fundos |
| `solicitante` | Contingência, Devolução |
| `criador` | Assinatura Eletrônica, Documento Processual |

Qualquer falha na cadeia (campo ausente, usuário sem e-mail) retorna `False`; nunca lança exceção.

---

## 8. Filtros Automáticos por Identidade

Diferentemente das guards acima, os filtros abaixo reduzem silenciosamente o queryset do painel conforme o perfil do usuário, sem expor registros de terceiros.

### 8.1 Painel de liquidações — fiscal de contrato

**Arquivo:** `pagamentos/views/pre_payment/liquidacoes/panels.py`

```python
if not is_backoffice:
    queryset_base = queryset_base.filter(liquidacao__fiscal_contrato=request.user)
```

Usuários sem `pagamentos.operador_contas_a_pagar` enxergam apenas os `DocumentoFiscal` cujas liquidações estão atribuídas a eles. Backoffice vê tudo.

### 8.2 Painel "Minhas Diárias" — beneficiário

**Arquivo:** `verbas_indenizatorias/views/diarias/panels.py`

```python
credor = Credor.objects.filter(usuario=request.user).first()
diarias = Diaria.objects.filter(beneficiario=credor)
```

O painel pessoal do credor exibe exclusivamente as diárias onde ele figura como beneficiário. Se não houver `Credor` vinculado ao usuário, o queryset retorna vazio.

### 8.3 Painel de autorização de diárias — proponente

**Arquivo:** `verbas_indenizatorias/services/autorizacao_diarias.py` → `listar_diarias_pendentes_para_proponente(usuario)`

```python
Diaria.objects.filter(proponente=usuario, status__status_choice__iexact=STATUS_VERBA_SOLICITADA)
```

O painel de autorização exibe apenas as diárias em que o usuário logado é o proponente e que estão no status `SOLICITADA`. Diárias de outros proponentes nunca aparecem, mesmo que o usuário possua permissões operacionais.

### 8.4 Minhas assinaturas eletrônicas

**Arquivo:** `pagamentos/views/support/signatures.py`

```python
meus_documentos = AssinaturaEletronica.objects.filter(criador=request.user)
```

A listagem de documentos para assinatura mostra apenas os documentos criados pelo próprio usuário. Admins/auditores acessam documentos específicos por outros caminhos (detalhe do processo).

---

## 9. Relação entre Controles e Perfis

| Funcionalidade | Credor/Suprido | Proponente | Fiscal Contrato | Operador Backoffice |
|---|---|---|---|---|
| Ver prestação de contas da própria diária | ✅ (ownership) | ❌ | ❌ | ✅ (permissão) |
| Autorizar diária | ❌ | ✅ (ownership obrigatório) | ❌ | ❌ |
| Vincular/desvincular diária a processo | ❌ | ❌ | ❌ | ✅ |
| Ver/editar processo de verbas (entidade própria) | — | ✅ (ownership) | — | ✅ |
| Lançar despesa / submeter prestação do suprimento | ✅ (ownership) | — | — | ✅ |
| Editar liquidação (ateste NF) | ❌ | — | ✅ (ownership) | ✅ |
| Disparar assinatura eletrônica | ✅ (se criador) | ✅ (se criador) | ✅ (se criador) | ✅ (se criador) |
| Ver painel de liquidações | ❌ | — | Apenas as suas | ✅ (todas) |
| Ver painel "Minhas Diárias" | Apenas as suas | — | — | — |
| Ver painel de autorização | — | Apenas as suas | — | — |
