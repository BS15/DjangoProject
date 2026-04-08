# FASE 1: Análise de Domínios e Fronteiras Lógicas

**Status**: Linha de base estabelecida (155 tests, 153 PASS)  
**Data**: 2026-04-08  
**Objetivo**: Preparar estrutura de pacotes canônicos por domínio sem mover tabelas ou quebrar imports.

---

## 1. Mapa de Pertenças por Domínio

### Domínio: FLUXO (Nuclear — Proceso + documento fiscal + auditoria + confiencialidad)

#### Views:
- `processos/views/fluxo/` (subdir completo)
- `processos/views/fluxo/api_views.py` (extract+barcode APIs)
- `processos/views/fluxo/pdf.py` (geração de autorização + PDF)
- `processos/views/fluxo/auditing/` (auditoria, API docs)
- `processos/views/fluxo/security.py` (download seguro)
- `processos/views/fluxo/support/` (helpers de fluxo: contingencias, devoluções, pendências)
- `processos/views/fluxo/pre_payment/` (A EMPENHAR até AGUARDANDO LIQUIDAÇÃO)
- `processos/views/fluxo/payment/` (A PAGAR até LANÇADO)
- `processos/views/fluxo/post_payment/` (CONFERÊNCIA até ARQUIVADO)

#### Services:
- `processos/services/fluxo/` (lógica de turnpike, transições, validações)
- `processos/utils/fluxo/` (utilitários de fluxo: contas, extraição)

#### Models:
- `Processo` (pivot nuclear)
- `StatusChoicesProcesso`, `FormasDePagamento`, `TiposDePagamento`
- `ReuniaoConselho`
- `Pendencia`, `Contingencia`, `Devolucao`
- `DocumentoDePagamento` (sub-entidades de comprovação)
- `Contrato` (se ainda existir)
- `AssinaturaAutentique` (com GenericForeignKey)

#### Permissões:
- `pode_operar_contas_pagar`
- `pode_autorizar_pagamento`
- `pode_auditar_conselho`
- `pode_arquivar`
- `pode_contabilizar`
- `pode_atestar_liquidacao`

#### Componentes Compartilhados:
- Modelos de **Cadastros** (Credor, ContasBancarias, Fornecedor, etc. — ficarão em `processos` por enquanto)
- Modelos fiscais: `DocumentoFiscal`, `RetencaoImposto`, etc. — ficarão em `processos` fiscais por enquanto
- History: `HistoricalRecords()` para rastreamento de edições

#### URLs (Zona Segura, nomes congelados):
- `/` — home
- `/adicionar/` — add_process
- `/processo/<id>/` — process_detail
- `/a-empenhar/` — a_empenhar
- `/contas-a-pagar/` — contas_a_pagar
- `/processos/conferencia/` — painel_conferencia
- `/processos/conselho/` — painel_conselho
- `/processos/arquivamento/` — painel_arquivamento
- `/api/processo/<id>/...` — API endpoints

---

### Domínio: VERBAS INDENIZATÓRIAS

#### Views:
- `processos/views/verbas/` (subdir completo)
- `processos/views/verbas/processo/` (agregação de verbas por processo)
- `processos/views/verbas/tipos/` (diárias, jetons, reembolsos, auxílios)

#### Services:
- `processos/services/verbas/` (lógica de cálculo, sincronização SISCAC)
- `processos/utils/verbas/diarias/` (importação/sync de diárias)

#### Models:
- `Diaria`, `StatusChoicesVerbasIndenizatorias`
- `Jeton`, `ReembolsoCombustivel`, `AuxilioRepresentacao`
- `MeiosDeTransporte` (lookup table)

#### Permissões:
- `pode_visualizar_verbas`
- `pode_gerenciar_processos_verbas`
- `pode_gerenciar_jetons`
- `pode_gerenciar_reembolsos`
- `pode_gerenciar_auxilios`
- `pode_importar_diarias`
- `pode_sincronizar_diarias_siscac`
- `pode_agrupar_verbas`

#### URLs:
- `/verbas/` — painel_verbas
- `/verbas/diarias/` — painel_diarias
- `/verbas/jetons/` — painel_jetons
- `/verbas/reembolsos/` — painel_reembolsos
- `/verbas/auxilios/` — painel_auxilios

#### Acoplamento com Fluxo:
- FK: `Diaria.processo` (apontando para `Processo`)
- N:1 com `Credor` (compartilhado)

---

### Domínio: SUPRIMENTOS DE FUNDOS

#### Views:
- `processos/views/suprimentos/` (subdir completo)
- `processos/views/suprimentos/cadastro/` (CRUD de suprimentos)
- `processos/views/suprimentos/prestacao_contas/` (accountability workflow)

#### Services:
- `processos/services/suprimentos/` (lógica de fluxo de prestação de contas)

#### Models:
- `SuprimentoDeFundos`, `StatusChoicesSuprimentoDeFundos`
- `PrestacaoDeContas` (se separado)

#### Permissões:
- `acesso_backoffice` (admin geral de suprimentos)
- Configuráveis por tipo de suprimento

#### URLs:
- `/suprimentos/` — painel_suprimentos
- `/suprimentos/cadastro/` — cadastro_suprimentos
- `/suprimentos/prestacao-contas/` — prestacao_contas

#### Acoplamento com Fluxo:
- FK: `SuprimentoDeFundos.processo`
- N:1 com `Credor` (compartilhado)

---

### Domínio: FISCAL (Fica em `processos` por enquanto)

#### Permanece em `processos` neste ciclo porque:
1. Tight coupling com `Processo` via FK bidirecional
2. Validações de liquidação e documentação fiscal são turnpike crítico
3. Modelo `DocumentoFiscal` é pivot para retenção, liquidação e comprovação

#### Models:
- `DocumentoFiscal`, `RetencaoImposto`, `CodigosImposto`

#### Views:
- `processos/views/fiscal/` (ainda em `processos`)

#### Permissões:
- `acesso_backoffice` (admin de fiscal)

---

### Domínio: CADASTROS E SISTEMAS AUXILIARES (Fica em `processos`)

#### Modelos Compartilhados:
- `Credor`, `ContasBancarias`, `Fornecedor`, `RazaoSocial`, `ContatoCredor`, `EndereçoCredor`

#### Views Auxiliares:
- `processos/views/cadastros.py` (CRUD de Credores, Contas)
- `processos/views/sistemas_auxiliares/` (imports, relatórios, sync)

#### Permissões:
- `acesso_backoffice` (geral)

#### URLs:
- `/cadastros/...` — Congelados, não mudam

---

## 2. Estratégia de Refatoração — FASE 1 (Sem Mover Tabelas)

### 2.1 Criar estrutura de pacotes canônicos

```
processos/
├── models/
│   ├── fluxo.py → re-export (compatibilidade temporária)
│   ├── verbas.py → re-export (compatibilidade temporária)
│   ├── suprimentos.py → re-export (compatibilidade temporária)
│   ├── cadastros.py → re-export (compatibilidade temporária)
│   └── segments/ (mantém tudo)
│
├── views/
│   ├── fluxo/ (já separado — deixar como está)
│   ├── verbas/ (já separado — deixar como está)
│   ├── suprimentos/ (já separado — deixar como está)
│   ├── fiscal/ (já separado — deixar como está)
│   ├── cadastros.py (será consolidado)
│   └── sistemas_auxiliares/ (consolidated)
│
├── services/
│   ├── fluxo/ (já separado)
│   ├── verbas/ (já separado)
│   ├── suprimentos/ (já separado)
│   ├── shared/ (compartilhado)
│   └── fiscal/ (fiscal-specific)
│
├── forms.py (ainda monolítico — dividir por domínio em Fase 2)
├── filters.py (ainda monolítico — dividir por domínio em Fase 2)
└── ...
```

### 2.2 Consolidar __init__.py por domínio

Criar re-export inteligente em cada domínio sem quebrar imports:

**`processos/views/fluxo/__init__.py`** (expandir):
```python
from . import api_views
from . import auditing
from . import security
from . import pdf
from .support.core import home_page, process_detail_view
from .pre_payment.cadastro import forms as pre_payment_forms
from .pre_payment.empenho import actions as pre_payment_actions
from .pre_payment.empenho import panels as pre_payment_panels
# ... etc

__all__ = [
    'api_views', 'auditing', 'security', 'pdf',
    'pre_payment_forms', 'pre_payment_actions', # via namespace
    ...
]
```

**Root `processos/views/__init__.py`** (criar):
```python
from . import fluxo
from . import verbas
from . import suprimentos
from . import fiscal
from . import cadastros
from . import sistemas_auxiliares

__all__ = ['fluxo', 'verbas', 'suprimentos', 'fiscal', 'cadastros', 'sistemas_auxiliares']
```

### 2.3 Formalizar serviços por domínio

**`processos/services/fluxo/__init__.py`**:
```python
from . import turnpike
from . import documentos
from .turnpike import advance_processo_status, validate_transitions
# ... re-exports canônicas

__all__ = ['advance_processo_status', 'validate_transitions', ...]
```

**`processos/services/verbas/__init__.py`**:
```python
from . import diarias
from . import calculo
# ...

__all__ = [...]
```

**Root `processos/services/__init__.py`** (criar):
```python
from . import fluxo
from . import verbas
from . import suprimentos
from . import shared
from . import fiscal

__all__ = ['fluxo', 'verbas', 'suprimentos', 'shared', 'fiscal']
```

### 2.4 Reexports de compatibilidade

Manter `processos/models/__init__.py` com:
```python
from .segments._fluxo_models import Processo, StatusChoicesProcesso, ...
from .segments._verbas_models import Diaria, Jeton, ...
from .segments._suprimentos_models import SuprimentoDeFundos, ...
from .segments._cadastros_models import Credor, ContasBancarias, ...
from .segments._fiscal_models import DocumentoFiscal, RetencaoImposto, ...

# Aliases para compatibilidade
from . import fluxo as fluxo_models  # re-export via segments
from . import verbas as verbas_models
from . import suprimentos as suprimentos_models
from . import cadastros as cadastros_models
from . import fiscal as fiscal_models

__all__ = [
    'Processo', 'StatusChoicesProcesso', # ... Fluxo canônicas
    'Diaria', 'Jeton', # ... Verbas
    'SuprimentoDeFundos', # ... Suprimentos
    'Credor', 'ContasBancarias', # ... Cadastros
    'DocumentoFiscal', # ... Fiscal
    # Modular imports
    'fluxo_models', 'verbas_models', 'suprimentos_models',
    'cadastros_models', 'fiscal_models'
]
```

---

## 3. Verificação de Estabilidade (Checkpoints)

| Checkpoint | Objetivo | Comando |
|-----------|----------|---------|
| 1. Imports Compilam | Sem SyntaxError/ImportError no Django bootstrap | `python manage.py check` |
| 2. URLs Resolvem | Sem quebra de named routes | `python manage.py show_urls` (visual) |
| 3. Testes Passam | Suite de testes é estável | `python manage.py test` |
| 4. Admin Funciona | Registro de modelos intacto | `python manage.py runserver` + browser |
| 5. Permissões Resolvem | RBAC não quebrado | `python manage.py shell` + test ContentType |
| 6. Migrações OK | Sem novas migrações geradas "acidentalmente" | `python manage.py makemigrations --dry-run` |

---

## 4. Próximos Passos (Fase 1 Actions)

### Action: Consolidar formalizações de canais de views por domínio

1. **Criar `processos/views/__init__.py`** com re-exports por domínio
2. Estender `processos/views/fluxo/__init__.py` para formalizar API pública
3. Estender `processos/views/verbas/__init__.py` para formalizar API pública
4. Estender `processos/views/suprimentos/__init__.py` para formalizar API pública
5. **Validar**: `manage.py check` + visual import test

### Action: Consolidar formalizações de services por domínio

1. **Criar `processos/services/__init__.py`** com re-exports
2. Formalizar `processos/services/fluxo/__init__.py`
3. Formalizar `processos/services/verbas/__init__.py`
4. Formalizar `processos/services/suprimentos/__init__.py`
5. **Validar**: import no shell, nenhuma regressão

### Action: Documentar Contratos de URL Congelados

1. Listar todos os `name=` em URLConfs (core.py, verbas.py, suprimentos.py, etc.)
2. Criar tabela de nomes que **NÃO MUDAM** durante Fase 1 e 2
3. Adicionar test que valida essas rotas (por segurança)

### Action: Documentar Matriz de Permissões

1. Tabela de `codename` x `app_label` (hoje tudo é `processos`)
2. Planejar re-namespace para Fase 2 (sem executar ainda)

---

## 5. Critério de Pronto (Done) para FASE 1

- [ ] `processos/views/__init__.py` criado e importa canonicamente
- [ ] `processos/services/__init__.py` criado e importa canonicamente
- [ ] `manage.py check` passa sem warnings/errors
- [ ] All 155 tests pass (ou fail count estável vs baseline)
- [ ] URL names congelados confirmados em documento separado
- [ ] Permissão matrix documentada (sem mudanças executadas)
- [ ] `PHASE1_COMPLETED.md` documentando mudanças e validações
- [ ] Pronto para PR review ou commit de estabilização

