# Contratos Congelados — URLs e Permissões (Fase 1 e Fase 2)

**Objetivo**: Documentar quais nomes de URL e codenames de permissão são contratos público-facing que **NÃO DEVEM MUDAR** durante a fragmentação de apps.

**Status**: Baseline estabelecido 2026-04-08

---

## 1. URLs Congeladas (Django named routes)

Estas rotas **devem funcionar identicamente** antes e depois da fragmentação:

### Fluxo Principal

| Nome | Padrão | Descrição | URLconf |
|------|--------|-----------|---------|
| `home_page` | `/` | Home view | core.py |
| `add_process` | `/adicionar/` | Add novo processo | core.py |
| `editar_processo` | `/processo/<id>/editar/` | Edit processo | core.py |
| `editar_processo_capa` | `/processo/<id>/editar/capa/` | Edit capa | core.py |
| `editar_processo_documentos` | `/processo/<id>/editar/documentos/` | Edit docs | core.py |
| `editar_processo_pendencias` | `/processo/<id>/editar/pendencias/` | Edit pendências | core.py |
| `visualizar_pdf_processo` | `/processo/<id>/pdf/` | View PDF | core.py |
| `process_detail` | `/processo/<id>/` | Detalhe de processo | core.py |

### Fluxo — Fases de Pagamento

#### A EMPENHAR (Pre-payment)

| Nome | Padrão | Descrição |
|------|--------|-----------|
| `a_empenhar` | `/a-empenhar/` | Painel A EMPENHAR |
| `registrar_empenho_action` | `/a-empenhar/registrar-empenho/` | POST registrar empenho |
| `avancar_para_pagamento` | `/processo/<id>/avancar-para-pagamento/` | Avanço para A PAGAR |

#### A PAGAR (Payment + Post-Payment)

| Nome | Padrão | Descrição |
|------|--------|-----------|
| `contas_a_pagar` | `/contas-a-pagar/` | Painel contas a pagar |
| `enviar_para_autorizacao` | `/processos/enviar-autorizacao/` | POST envio |
| `painel_autorizacao` | `/processos/autorizacao/` | Painel autorizacao |
| `autorizar_pagamento` | `/processos/autorizar-pagamento/` | POST autorizar |
| `recusar_autorizacao` | `/processos/autorizacao/<id>/recusar/` | POST recusar |

#### Conferência e Contabilização

| Nome | Padrão | Descrição |
|------|--------|-----------|
| `painel_conferencia` | `/processos/conferencia/` | Painel conferência |
| `iniciar_conferencia` | `/processos/conferencia/iniciar/` | POST iniciar |
| `conferencia_processo` | `/processos/conferencia/<id>/revisar/` | Review conferência |
| `aprovar_conferencia` | `/processos/conferencia/<id>/aprovar/` | POST aprovar |
| `painel_contabilizacao` | `/processos/contabilizacao/` | Painel contabilização |
| `iniciar_contabilizacao` | `/processos/contabilizacao/iniciar/` | POST iniciar |
| `contabilizacao_processo` | `/processos/contabilizacao/<id>/revisar/` | Review |
| `aprovar_contabilizacao` | `/processos/contabilizacao/<id>/aprovar/` | POST aprovar |
| `recusar_contabilizacao` | `/processos/contabilizacao/<id>/recusar/` | POST recusar |

#### Conselho Fiscal e Arquivamento

| Nome | Padrão | Descrição |
|------|--------|-----------|
| `painel_conselho` | `/processos/conselho/` | Painel conselho |
| `conselho_processo` | `/processos/conselho/<id>/revisar/` | Review |
| `aprovar_conselho` | `/processos/conselho/<id>/aprovar/` | POST aprovar |
| `recusar_conselho` | `/processos/conselho/<id>/recusar/` | POST recusar |
| `gerar_parecer_conselho` | `/processo/<id>/parecer-conselho/` | Gerar parecer PDF |
| `gerenciar_reunioes` | `/processos/conselho/reunioes/` | Painel reuniões |
| `gerenciar_reunioes_action` | `/processos/conselho/reunioes/criar/` | POST criar |
| `montar_pauta_reuniao` | `/processos/conselho/reunioes/<id>/montar-pauta/` | Montar pauta |
| `montar_pauta_reuniao_action` | `/processos/conselho/reunioes/<id>/montar-pauta/adicionar/` | POST |
| `analise_reuniao` | `/processos/conselho/reunioes/<id>/analisar/` | Análise |
| `iniciar_conselho_reuniao` | `/processos/conselho/reunioes/<id>/iniciar/` | POST iniciar |
| `painel_arquivamento` | `/processos/arquivamento/` | Painel arquivamento |
| `arquivar_processo` | `/processos/arquivamento/<id>/aprovar/` | Arquivar review |
| `arquivar_processo_action` | `/processos/arquivamento/<id>/executar/` | POST |

#### Lançamento Bancário

| Nome | Padrão | Descrição |
|------|--------|-----------|
| `separar_para_lancamento_bancario` | `/processos/separar-lancamento/` | POST |
| `lancamento_bancario` | `/processos/lancamento-bancario/` | Painel |
| `marcar_como_lancado` | `/processos/marcar-lancado/` | POST marcar |
| `desmarcar_lancamento` | `/processos/desmarcar-lancamento/` | POST desmarcar |

### Verbas Indenizatórias

Prefixed com `/verbas/`:

| Nome | Padrão | Descrição |
|------|--------|-----------|
| `painel_verbas` | `/verbas/` | Painel geral |
| `diarias_list_view` | `/verbas/diarias/` | Painel diárias |
| `add_diaria_view` | `/verbas/diarias/adicionar/` | Add diária |
| `edit_diaria_view` | `/verbas/diarias/<id>/editar/` | Edit diária |
| `jetons_list_view` | `/verbas/jetons/` | Painel jetons |
| `add_jeton_view` | `/verbas/jetons/adicionar/` | Add jeton |
| `edit_jeton_view` | `/verbas/jetons/<id>/editar/` | Edit jeton |
| `reembolsos_list_view` | `/verbas/reembolsos/` | Painel reembolsos |
| `add_reembolso_view` | `/verbas/reembolsos/adicionar/` | Add reembolso |
| `edit_reembolso_view` | `/verbas/reembolsos/<id>/editar/` | Edit reembolso |
| `auxilios_list_view` | `/verbas/auxilios/` | Painel auxílios |
| `add_auxilio_view` | `/verbas/auxilios/adicionar/` | Add auxílio |
| `edit_auxilio_view` | `/verbas/auxilios/<id>/editar/` | Edit auxílio |
| `agrupar_verbas_view` | `/verbas/agrupar/` | Agrupar verbas |

### Suprimentos de Fundos

Prefixed com `/suprimentos/`:

| Nome | Padrão | Descrição |
|------|--------|-----------|
| `painel_suprimentos` | `/suprimentos/` | Painel geral |
| (Mais a confirmar em análise) | | |

### Sistemas Auxiliares e Sync

| Nome | Padrão | Descrição |
|------|--------|-----------|
| `sincronizar_siscac` | `/fluxo/sincronizar-siscac/` | View sync |
| `sincronizar_siscac_manual_action` | `/fluxo/sincronizar-siscac/manual/` | POST manual |
| `sincronizar_siscac_auto_action` | `/fluxo/sincronizar-siscac/auto/` | POST auto |
| `painel_pendencias` | `/pendencias/` | Painel pendências |
| `painel_contingencias` | `/contingencias/` | Painel contingências |
| `add_contingencia` | `/contingencias/nova/` | Add |
| `add_contingencia_action` | `/contingencias/nova/enviar/` | POST |
| `analisar_contingencia` | `/contingencias/<id>/analisar/` | Análise |
| `painel_devolucoes` | `/devolucoes/` | Painel devoluções |
| `registrar_devolucao` | `/processo/<id>/devolucao/` | Register |
| `registrar_devolucao_action` | `/processo/<id>/devolucao/salvar/` | POST |
| `auditoria` | `/auditoria/` | Painel auditoria |
| `download_arquivo_seguro` | `/documentos/secure/<tipo>/<id>/` | Download seguro |

### APIs e Endpoints Técnicos

| Nome | Padrão | Descrição |
|------|--------|-----------|
| `api_extrair_codigos_barras_processo` | `/api/processo/<id>/extrair-codigos-barras/` | Barcode extraction |
| `api_extrair_codigos_barras_upload` | `/api/extrair-codigos-barras-upload/` | Upload → extract |
| `api_extrair_dados_empenho` | `/api/extrair-dados-empenho/` | Empenho data extraction |
| `api_documentos_pagamento` | `/api/documentos-por-pagamento/` | Doc types por pagamento |
| `api_detalhes_pagamento` | `/api/detalhes-pagamento/` | Payment details JSON |
| `api_documentos_processo` | `/api/processo/<id>/documentos/` | Docs list |
| `api_processo_detalhes` | `/api/processo_detalhes/` | Processo details JSON |
| `gerar_autorizacao_pagamento` | `/processo/<id>/autorizacao-pagamento/` | Gerar autorização PDF |

---

## 2. Permissões (Codenames) Congeladas

Estas permissões **devem manter seus codenames** durante fragmentação. O `app_label` mudará em Fase 2, mas o `codename` não.

### Permissões de Fluxo

| Codename | Descrição | Usado em |
|----------|-----------|----------|
| `pode_operar_contas_pagar` | Acesso geral a operações de c/c | views/fluxo/payment/* |
| `pode_autorizar_pagamento` | Autorizar pagamentos | post_payment/contabilização |
| `pode_auditar_conselho` | Acesso painel conselho | post_payment/conselho/* |
| `pode_arquivar` | Executar arquivamento | post_payment/arquivamento/* |
| `pode_contabilizar` | Executar contabilização | post_payment/contabilização/* |
| `pode_atestar_liquidacao` | Atestar liquidação fiscal | pre_payment/liquidações |

### Permissões de Verbas

| Codename | Descrição | Usado em |
|----------|-----------|----------|
| `pode_visualizar_verbas` | Ver painéis de verbas | views/verbas/* |
| `pode_gerenciar_processos_verbas` | CRUD verbas em processo | views/verbas/processo/* |
| `pode_gerenciar_jetons` | CRUD jetons | views/verbas/tipos/jetons/* |
| `pode_gerenciar_reembolsos` | CRUD reembolsos | views/verbas/tipos/reembolsos/* |
| `pode_gerenciar_auxilios` | CRUD auxílios | views/verbas/tipos/auxilios/* |
| `pode_importar_diarias` | Importar diárias via upload | sistemas_auxiliares/imports/diarias |
| `pode_sincronizar_diarias_siscac` | Sincronizar SISCAC → DB | sistemas_auxiliares/sync/diarias |
| `pode_agrupar_verbas` | Agrupar/desagrupar | views/verbas/processo/actions |

### Permissões Administrativas

| Codename | Descrição | Usado em |
|----------|-----------|----------|
| `acesso_backoffice` | Admin geral de sistema | cadastros, contextos, contas fixas |

---

## 3. Validação de Estabilidade de Contratos

### Test: URL Names Resolvem

```python
# Em test ou shell
from django.urls import reverse

names = [
    'home_page', 'add_process', 'a_empenhar', 
    'painel_conselho', 'painel_verbas', ...
]

for name in names:
    try:
        url = reverse(name, ...)  # com kwargs apropriados
        print(f"✓ {name}: {url}")
    except:
        print(f"✗ {name}: BROKEN")
```

### Test: Permissões Resolvem

```python
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

codenames = [
    'pode_operar_contas_pagar', 'pode_autorizar_pagamento',
    'pode_visualizar_verbas', ...
]

for codename in codenames:
    perm = Permission.objects.filter(codename=codename).first()
    if perm:
        print(f"✓ {codename}: app_label={perm.content_type.app_label}")
    else:
        print(f"✗ {codename}: NOT FOUND")
```

---

## 4. Impacto de Mudanças (Pós-Fragmentação)

Quando migramos modelos para novos apps em Fase 2:

### O que **NÃO MUDA** (garantido):
- Nome de URL (Django `name=` field)
- Path de URL (rota HTTP)
- Permissões `codename` (apenas `app_label` muda)
- Admin interface (permanece ok se reexports mantidos)

### O que **PODE MUDAR** (cuidado):
- `Content-Type` IDs em banco de dados (se migrar tabelas)
- `Permission` app_label (será migrado por data migration)
- Admin URLs internos (ex.: `admin:fluxo_processo_change` vs `admin:processos_processo_change`)

### Estratégia de Compatibilidade:
1. **Manter re-exports** em `processos.models.*` entre fase 1 e 2
2. **Manter URLConfs unificadas** enquanto migram para novos apps
3. **Data migration** para ContentType + Permission (antes de produção)
4. **URLs de admin** — decidir se permanece agregada ou refatora por app

---

## 5. Checklist — Before/After

### Fase 1 (Hoje) — Antes de Fragmentação

- [ ] Todos os `name=` em URLConfs funcionam
- [ ] `python manage.py show_urls` lista todas as rotas esperadas
- [ ] `Permission.objects.all()` tem todos os codenames esperados
- [ ] Testes de smoke routes passes
- [ ] Manual testing de navegação funciona

### Fase 2 & Depois — Após Fragmentação de Models

- [ ] **Todos os `name=` continuam funcionando** (invariante)
- [ ] Admin para novos apps está online
- [ ] `Permission` objectos resolvem com novo `app_label` (Fluxo, Verbas, etc.)
- [ ] Smoke tests ainda fazem reverse() de todos os names
- [ ] Histórico de audição está intacto

---

## 6. Leitura Recomendada

- [Código cores com URLs congeladas](DjangoProject/urlconf/core.py)
- [Comando setup_grupos (que estabelece permissões originais)](processos/management/commands/setup_grupos.py)
- [Testes de smoke de URL](processos/tests/) — criar se não existir

