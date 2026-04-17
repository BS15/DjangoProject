# Processos App - Comprehensive Structure Inventory

**Generated:** April 8, 2026 | **Total Files Analyzed:** 200+

---

## 📊 Executive Summary

| Component | Count | Status |
|-----------|-------|--------|
| **Model Files (segments/)** | 5 | ✅ Organized |
| **View Files** | 126 | ✅ Well-structured |
| **Form Classes** | 12+ | ✅ Complete |
| **FilterSet Classes** | 14 | ✅ Comprehensive |
| **Migrations** | 88 | ✅ Critical chain |
| **Service Modules** | 14 | ✅ Segmented |
| **Utility Modules** | 15 | ✅ Logical grouping |
| **Management Commands** | 3 | ✅ Active |
| **Test Modules** | 10 | ✅ Coverage |

---

## 1️⃣ MODELS STRUCTURE (processos/models/)

### Directory Architecture
```
processos/models/
├── __init__.py               [Re-exports all segmented models]
├── fluxo.py                 [Re-export from segments/_fluxo_models.py]
├── fiscal.py                [Re-export from segments/_fiscal_models.py]
├── verbas.py                [Re-export from segments/_verbas_models.py]
├── suprimentos.py           [Re-export from segments/_suprimentos_models.py]
├── cadastros.py             [Re-export from segments/_cadastros_models.py]
└── segments/                [SEGMENTED: Domain-based separation]
    ├── _fluxo_models.py           [892 lines]
    ├── _fiscal_models.py          [268 lines]
    ├── _verbas_models.py          [280 lines]
    ├── _suprimentos_models.py     [151 lines]
    ├── _cadastros_models.py       [188 lines]
    ├── auxiliary.py              [Re-exports auxiliary models]
    ├── documents.py              [Re-exports document models]
    ├── core.py                   [Re-exports core domain models]
    ├── parametrizations.py        [Catalog/configuration models]
    └── auditing.py               [Audit trail & historical records]
```

---

### 1.1 MODEL CLASSES BY DOMAIN

#### **DOMAIN: Fluxo (Financial Flow)**
**File:** `processos/models/segments/_fluxo_models.py` (892 lines)

| Model Class | Purpose | Key Relations |
|-------------|---------|----------------|
| `Processo` | Main entity for budget execution & payment cycle | FK: Credor, links all domain entities |
| `DocumentoOrcamentario` | Budget document (Empenho) tracking | FK: Processo |
| `Boleto_Bancario` | Payment document wrapper | FK: Processo |
| `DocumentoBase` | Abstract base for all document types | - |
| `ReuniaoConselho` | Council meeting for batch process review | Timestamps & status tracking |
| `Pendencia` | Blockers/issues per processo | FK: Processo, StatusChoicesPendencias |
| `Contingencia` | Contingency record for payment issues | FK: Processo, workflow stages |
| `RegistroAcessoArquivo` | File access audit log | Security & compliance tracking |
| `Devolucao` | Fund return record | FK: Processo |
| `AssinaturaAutentique` | Digital signature from Autentique service | Generic relation to multiple entities |

**Key Features:**
- Full audit trail via `HistoricalRecords()`
- Turnpike pattern: Strict state machine transitions
- File upload handling via `caminho_documento()` utility
- Permission model class Meta with 15+ permission definitions

---

#### **DOMAIN: Fiscal (Tax & Fiscal)**
**File:** `processos/models/segments/_fiscal_models.py` (268 lines)

| Model Class | Purpose | Key Relations |
|-------------|---------|----------------|
| `CodigosImposto` | Tax code registry with REINF metadata | regra_competencia, serie_reinf, aliquota |
| `StatusChoicesRetencoes` | Tax retention status catalog | Choices for RetencaoImposto |
| `DocumentoFiscal` | Invoice/fiscal document linked to processo | FK: Processo, Credor (emitente), User (fiscal), Boleto_Bancario |
| `RetencaoImposto` | Individual tax withheld from payment | FK: DocumentoFiscal or Processo, CodigosImposto, Credor (beneficiary) |
| `ComprovanteDePagamento` | Payment proof/receipt document | FK: Processo, file upload |

**Key Features:**
- CPF/CNPJ validation with basic regex rules
- Invoice uniqueness constraint: `(processo, numero_nota_fiscal, serie_nota_fiscal)`
- REINF series mapping: S2000 (INSS) | S4000 (IR/CSLL/PIS/COFINS)
- Fiscal contrato assignment for attestation

---

#### **DOMAIN: Verbas Indenizatorias (Allowances)**
**File:** `processos/models/segments/_verbas_models.py` (280 lines)

| Model Class | Purpose | Key Relations |
|-------------|---------|----------------|
| `StatusChoicesVerbasIndenizatorias` | Status catalog (A EMPENHAR, AGUARDANDO LIQUIDAÇÃO, A PAGAR, etc.) | - |
| `TiposDeVerbasIndenizatorias` | Verba type catalog (Diária, Jeton, Reembolso, Auxílio) | - |
| `MeiosDeTransporte` | Transport type for diárias (Aéreo, Terrestre, Aquático) | - |
| `Tabela_Valores_Unitarios_Verbas_Indenizatorias` | Unit value table per verba type & position | FK: TiposDeVerbasIndenizatorias, CargosFuncoes |
| `Diaria` | Travel allowance with auto-calculated value | FK: Processo, Credor (beneficiario), User (proponente), MeiosDeTransporte |
| `DocumentoDiaria` | Supporting docs for diária (receipts, etc.) | FK: Diaria |
| `ReembolsoCombustivel` | Fuel reimbursement linked to travel | FK: Processo, Diaria (optional), Credor |
| `DocumentoReembolso` | Supporting docs for reembolso | FK: ReembolsoCombustivel |
| `Jeton` | Session/meeting attendance fee | FK: Processo, Credor, ReuniaoConselho |
| `DocumentoJeton` | Supporting docs for jeton | FK: Jeton |
| `AuxilioRepresentacao` | Representation allowance | FK: Processo, Credor |
| `DocumentoAuxilio` | Supporting docs for auxílio | FK: AuxilioRepresentacao |

**Key Features:**
- Per-verba-type document models (DocumentoDiaria, DocumentoReembolso, etc.)
- Auto-calculated value from position-based unit values
- SISCAC integration: `numero_siscac` field tracks external system sync
- Autentique digital signature support via `assinaturas_autentique` GenericRelation
- Full history tracking for compliance

---

#### **DOMAIN: Suprimentos (Petty Cash/Advance Funds)**
**File:** `processos/models/segments/_suprimentos_models.py` (151 lines)

| Model Class | Purpose | Key Relations |
|-------------|---------|----------------|
| `StatusChoicesSuprimentoDeFundos` | Suprimento lifecycle status catalog | - |
| `SuprimentoDeFundos` | Petty cash advance with accountability closure | FK: Processo, Credor (suprido), dynamic properties for balance |
| `DespesaSuprimento` | Individual expense within suprimento | FK: SuprimentoDeFundos, arquivo field |
| `DocumentoSuprimentoDeFundos` | General document for suprimento (outside despesas) | FK: SuprimentoDeFundos |

**Key Features:**
- Dynamic properties: `valor_gasto`, `saldo_remanescente` (computed on-the-fly)
- Prestação de Contas (accountability) closure phase required before finalization
- Tax field: PF-only suprido constraint (`limit_choices_to={'tipo': 'PF'}`)
- Single arquivo field per expense (unified Solicitação + NF scan)

---

#### **DOMAIN: Cadastros (Registries)**
**File:** `processos/models/segments/_cadastros_models.py` (188 lines)

| Model Class | Purpose | Key Relations |
|-------------|---------|----------------|
| `Credor` | Entity favored in payments (supplier/person) | FK: ContasBancarias, CargosFuncoes; tipo=PF/PJ/EX |
| `ContasBancarias` | Bank account for creditor | FK: Credor |
| `CargosFuncoes` | Position/role catalog for classification | grupo (grouping field) |
| `ContaFixa` | Fixed recurring account (utilities, services) | FK: Credor |
| `DadosContribuinte` | Contributor data (person or entity) | Likely for external integrations |
| `FaturaMensal` | Monthly billing tied to fixed account | FK: ContaFixa |

**Key Features:**
- CPF/CNPJ validation with repetition checks
- Credor type system: PF (individual), PJ (company), EX (foreign/other)
- GroupBy grouping for functional organization
- Full audit trail on all entities

---

### 1.2 Model Architecture Patterns

```json
{
  "model_segregation": {
    "fluxo": {
      "responsibility": "Core workflow, state machine, audit",
      "files": 1,
      "models": 10,
      "lines": 892
    },
    "fiscal": {
      "responsibility": "Tax handling, invoices, retentions",
      "files": 1,
      "models": 5,
      "lines": 268
    },
    "verbas": {
      "responsibility": "Allowances and indemnities",
      "files": 1,
      "models": 12,
      "lines": 280
    },
    "suprimentos": {
      "responsibility": "Petty cash and advance management",
      "files": 1,
      "models": 4,
      "lines": 151
    },
    "cadastros": {
      "responsibility": "Registries and masters",
      "files": 1,
      "models": 6,
      "lines": 188
    }
  },
  "total_models": 37,
  "total_lines": 1779,
  "re_export_layer": "Compatibility wrappers in processos/models/{domain}.py"
}
```

---

## 2️⃣ VIEWS STRUCTURE (processos/views/)

### Directory Tree (126 Python files)
```
processos/views/
├── __init__.py                   [Packaging & imports]
├── cadastros.py                  [Credor/ContasBancarias CRUD]
├── chaos.py                      [Debug & testing endpoints]
├── desenvolvedor.py              [Fake data generators]
├── fiscal/
│   ├── __init__.py
│   └── fiscal_retencoes.py      [Tax retention management]
├── fluxo/                         [MAIN WORKFLOW - 82 files]
│   ├── __init__.py
│   ├── api_views.py             [JSON API endpoints]
│   ├── pdf.py                   [PDF document generation]
│   ├── security.py              [File access & permission checks]
│   ├── shared.py                [Common rendering utilities]
│   ├── auditing/                [Audit trail views]
│   │   ├── __init__.py
│   │   ├── apis.py              [Audit REST endpoints]
│   │   └── panels.py            [Audit UI panels]
│   ├── helpers/                 [Business logic helpers]
│   │   ├── __init__.py
│   │   ├── archival.py          [Archive workflow logic]
│   │   ├── audit_builders.py    [Audit record construction]
│   │   ├── contingencias.py     [Contingency handling]
│   │   ├── errors.py            [Error handling utilities]
│   │   ├── payment_builders.py  [Payment flow assembly]
│   │   ├── queries.py           [Optimized DB queries]
│   │   └── workflows.py         [State machine transitions]
│   ├── payment/                  [PAYMENT STAGE - Multi-level workflows]
│   │   ├── __init__.py
│   │   ├── autorizacao/         [Authorization stage]
│   │   │   ├── __init__.py
│   │   │   ├── actions.py       [Authorization actions]
│   │   │   └── panels.py        [Authorization UI views]
│   │   ├── lancamento/          [Launch/recording stage]
│   │   │   ├── __init__.py
│   │   │   ├── actions.py
│   │   │   └── panels.py
│   │   ├── contas_a_pagar/      [Accounts payable stage]
│   │   │   ├── __init__.py
│   │   │   ├── actions.py
│   │   │   └── panels.py
│   │   └── comprovantes/        [Payment proof handling]
│   │       ├── __init__.py
│   │       ├── actions.py
│   │       └── panels.py
│   ├── post_payment/             [POST-PAYMENT STAGE]
│   │   ├── __init__.py
│   │   ├── arquivamento/        [Archival stage (final)]
│   │   │   ├── __init__.py
│   │   │   ├── actions.py
│   │   │   ├── panels.py
│   │   │   └── reviews.py       [Council archival review]
│   │   ├── conferencia/         [Review/verification stage]
│   │   │   ├── __init__.py
│   │   │   ├── actions.py
│   │   │   ├── panels.py
│   │   │   └── reviews.py
│   │   ├── conselho/            [Council fiscal review]
│   │   │   ├── __init__.py
│   │   │   ├── actions.py
│   │   │   ├── panels.py
│   │   │   ├── pdf.py           [Council report generation]
│   │   │   └── reviews.py
│   │   ├── contabilizacao/      [Accounting alignment stage]
│   │   │   ├── __init__.py
│   │   │   ├── actions.py
│   │   │   ├── panels.py
│   │   │   └── reviews.py
│   │   └── reunioes/            [Council meeting management]
│   │       ├── __init__.py
│   │       ├── actions.py
│   │       └── panels.py
│   ├── pre_payment/              [PRE-PAYMENT STAGE]
│   │   ├── __init__.py
│   │   ├── cadastro/            [Process registration]
│   │   │   ├── __init__.py
│   │   │   ├── documentos.py    [Supporting document upload]
│   │   │   └── forms.py         [Registration forms]
│   │   ├── empenho/             [Budget allocation]
│   │   │   ├── __init__.py
│   │   │   ├── actions.py
│   │   │   └── panels.py
│   │   ├── liquidacoes/         [Invoice settlement]
│   │   │   ├── __init__.py
│   │   │   ├── actions.py
│   │   │   └── panels.py
│   │   └── helpers.py           [Pre-payment utilities]
│   └── support/                  [SUPPORT & AUX FEATURES]
│       ├── __init__.py
│       ├── contingencia/        [Contingency handling]
│       │   ├── __init__.py
│       │   ├── actions.py
│       │   ├── helpers.py
│       │   └── panels.py
│       ├── devolucao/           [Fund return handling]
│       │   ├── __init__.py
│       │   ├── actions.py
│       │   └── panels.py
│       ├── pendencia/           [Issue/blocker tracking]
│       │   ├── __init__.py
│       │   └── panels.py
│       └── core/                [Support core utilities]
│           ├── __init__.py
│           └── helpers.py
├── shared.py                    [Shared rendering helpers]
├── signature_access.py          [Signature file access control]
├── suprimentos/                  [PETTY CASH MODULE]
│   ├── __init__.py
│   ├── cadastro/                [Suprimento registration]
│   │   ├── __init__.py
│   │   └── forms.py
│   ├── helpers.py
│   └── prestacao_contas/        [Accountability/closure]
│       ├── __init__.py
│       └── actions.py
├── verbas/                       [ALLOWANCES MODULE - 26 files]
│   ├── __init__.py              [Re-exports for compatibility]
│   ├── processo.py              [Cross-verba processo views]
│   ├── verbas_shared.py         [Shared verba utilities]
│   ├── tipos/                   [Type-specific verba views]
│   │   ├── diarias.py           [Diária CRUD & list]
│   │   ├── jetons.py            [Jeton CRUD & list]
│   │   ├── reembolsos.py        [Reembolso CRUD & list]
│   │   └── auxilios.py          [Auxílio CRUD & list]
│   └── processo/
│       ├── __init__.py
│       └── [...verba-processo integration views...]
├── contas/                       [BANK ACCOUNT MODULE]
│   └── [Empty: Only __pycache__]
├── sistemas_auxiliares/          [AUXILIARY SYSTEMS - 18 files]
│   ├── __init__.py
│   ├── assinaturas.py           [Autentique signature management]
│   ├── contas/                  [Fixed account management]
│   │   ├── __init__.py
│   │   ├── actions.py
│   │   ├── forms.py
│   │   └── panels.py
│   ├── imports/                 [Batch import handlers]
│   │   ├── __init__.py
│   │   ├── credores.py          [Credor import]
│   │   └── diarias.py           [Diária import]
│   ├── relatorios.py            [Report generation]
│   └── sync/                    [Data synchronization]
│       ├── __init__.py
│       ├── diarias.py           [SISCAC sync for diárias]
│       └── pagamentos.py        [Payment sync]
├── teste_pdf.py                 [PDF testing endpoint]
└── desenvolvedor.py             [Developer utilities]
```

---

### 2.1 Views Summary by Domain

```json
{
  "fluxo": {
    "count": 82,
    "responsibility": "Main workflow, payment stages, audit",
    "key_view_layers": [
      "Payment stage actions (autorizacao, lancamento, contas_a_pagar, comprovantes)",
      "Post-payment stages (arquivamento, conferencia, conselho, contabilizacao)",
      "Pre-payment stages (cadastro, empenho, liquidacoes)",
      "Support modules (contingencia, devolucao, pendencia)",
      "API views & security"
    ]
  },
  "verbas": {
    "count": 26,
    "responsibility": "Allowance types CRUD and processo integration",
    "key_view_layers": [
      "Per-type views (diarias, jetons, reembolsos, auxilios)",
      "Cross-verba processo handling",
      "Shared utility functions"
    ]
  },
  "suprimentos": {
    "count": 8,
    "responsibility": "Petty cash registration and accountability",
    "key_view_layers": [
      "Cadastro (registration)",
      "Prestacao de Contas (accountability closure)"
    ]
  },
  "fiscal": {
    "count": 2,
    "responsibility": "Tax management and REINF export",
    "key_view_layers": [
      "REINF XML generation",
      "Tax retention management"
    ]
  },
  "sistemas_auxiliares": {
    "count": 18,
    "responsibility": "External integrations and batch operations",
    "key_view_layers": [
      "Autentique signature management",
      "Fixed account (ContaFixa) management",
      "Batch imports (credores, diárias)",
      "SISCAC and payment sync",
      "Report generation"
    ]
  },
  "cadastros": {
    "count": 1,
    "responsibility": "Master data CRUD for credores and accounts",
    "key_view_layers": [
      "Credor registration",
      "Bank account management"
    ]
  },
  "other": {
    "count": 11,
    "responsibility": "Shared, testing, developer utilities",
    "key_view_layers": [
      "shared.py (common rendering)",
      "signature_access.py (file security)",
      "chaos.py (debug)",
      "teste_pdf.py (testing)",
      "desenvolvedor.py (dev data)"
    ]
  },
  "total_count": 126
}
```

---

## 3️⃣ FORMS STRUCTURE (processos/forms.py)

**File:** `processos/forms.py` (Single monolithic file)

### Form Classes Identified (12+)

| Form Class | Domain | Purpose | Key Fields |
|-----------|--------|---------|-----------|
| `ProcessoForm` | Fluxo | Main processo creation/edit | n_nota_empenho, data_pagamento, valor_bruto, valor_liquido, etc. |
| `DocumentoFiscalForm` | Fiscal | Invoice/nota fiscal entry | numero_nota_fiscal, serie_nota_fiscal, valor_bruto, atestada, etc. |
| `Boleto_BancarioForm` | Fluxo | Payment document form | tipo, ordem, arquivo |
| `RetencaoImpostoForm` | Fiscal | Tax withheld input | beneficiario, codigo, rendimento_tributavel, valor |
| `CredorForm` | Cadastros | Creditor/supplier registry | cpf_cnpj, nome, telefone, email, chave_pix, etc. |
| `DiariaForm` | Verbas | Travel allowance entry | numero_siscac, processo, (implicitly calculated valor_total) |
| `ReembolsoForm` | Verbas | Fuel reimbursement | - |
| `JetonForm` | Verbas | Session fee entry | - |
| `AuxilioForm` | Verbas | Representation allowance | - |
| `SuprimentoForm` | Suprimentos | Petty cash registration | suprido, lotacao, valor_liquido, taxa_saque, data_saida, data_retorno |
| `DespesaSuprimentoForm` | Suprimentos | Individual expense | data, estabelecimento, detalhamento, nota_fiscal, valor |
| `PendenciaForm` | Fluxo | Issue/blocker tracking | - |

**Architectural Notes:**
- All forms extend Django's `forms.ModelForm`
- Heavy use of Bootstrap CSS classes for styling
- Brazilian input masking: CPF/CNPJ (`mask-cpf-cnpj`), phone (`mask-telefone`), currency (R$)
- Inline formsets for related document uploads

---

## 4️⃣ FILTERS STRUCTURE (processos/filters.py)

**File:** `processos/filters.py` (Single structured file)

### FilterSet Classes (14 total)

```json
{
  "base": {
    "class": "BaseStyledFilterSet",
    "parent": "django_filters.FilterSet",
    "purpose": "Adds Bootstrap styling to all filters"
  },
  "filters": [
    {
      "name": "ProcessoFilter",
      "domain": "fluxo",
      "model": "Processo",
      "fields": ["numero_sequencial", "credor", "status", "data_empenho", "valor_liquido"]
    },
    {
      "name": "CredorFilter",
      "domain": "cadastros",
      "model": "Credor",
      "fields": ["nome", "cpf_cnpj", "tipo"]
    },
    {
      "name": "DiariaFilter",
      "domain": "verbas",
      "model": "Diaria",
      "fields": ["numero_sequencial", "beneficiario", "status"]
    },
    {
      "name": "ReembolsoFilter",
      "domain": "verbas",
      "model": "ReembolsoCombustivel",
      "fields": ["numero_sequencial", "beneficiario", "status"]
    },
    {
      "name": "JetonFilter",
      "domain": "verbas",
      "model": "Jeton",
      "fields": ["numero_sequencial", "beneficiario", "reuniao", "status"]
    },
    {
      "name": "AuxilioFilter",
      "domain": "verbas",
      "model": "AuxilioRepresentacao",
      "fields": ["numero_sequencial", "beneficiario", "status"]
    },
    {
      "name": "RetencaoNotaFilter",
      "domain": "fiscal",
      "model": "RetencaoImposto",
      "fields": ["documento_fiscal", "beneficiario", "codigo"],
      "note": "Grouped by invoice (DocumentoFiscal)"
    },
    {
      "name": "RetencaoProcessoFilter",
      "domain": "fiscal",
      "model": "RetencaoImposto",
      "fields": ["processo", "beneficiario", "codigo"],
      "note": "Grouped by processo"
    },
    {
      "name": "RetencaoIndividualFilter",
      "domain": "fiscal",
      "model": "RetencaoImposto",
      "fields": ["beneficiario", "codigo", "data_retencao"],
      "note": "Fine-grained individual view"
    },
    {
      "name": "PendenciaFilter",
      "domain": "fluxo",
      "model": "Pendencia",
      "fields": ["processo", "credor", "tipo"]
    },
    {
      "name": "DocumentoFiscalFilter",
      "domain": "fiscal",
      "model": "DocumentoFiscal",
      "fields": ["processo", "cnpj_emitente", "data_emissao"]
    },
    {
      "name": "DevolucaoFilter",
      "domain": "fluxo",
      "model": "Devolucao",
      "fields": ["processo", "data_devolucao"]
    },
    {
      "name": "ContingenciaFilter",
      "domain": "fluxo",
      "model": "Contingencia",
      "fields": ["processo", "tipo", "status"]
    }
  ],
  "total_count": 14,
  "pattern": "One FilterSet per primary model"
}
```

---

## 5️⃣ MIGRATIONS STRUCTURE (processos/migrations/)

### Migration Statistics

| Metric | Value |
|--------|-------|
| **Total Migrations** | 88 |
| **Latest Migration** | 0083_remove_criado_em_documento_orcamentario.py |
| **First Migration** | 0001_initial.py |
| **Major Schema Events** | 83 |

### Critical Migration Chain Analysis

#### Phase 1: Core Models (0001-0020)
- 0001_initial.py - Schema bootstrap
- 0006_codigosimposto_formasdepagamento_statuschoices_and_more.py - Catalog tables
- 0012_tiposdeverbasindenizatorias_and_more.py - Verbas infrastructure
- 0016_contasbancarias_and_more.py - Bank account system
- 0020_verba_indenizatoria_valor.py - Value field additions

#### Phase 2: Model Restructuring (0021-0040)
- 0021_grupos_rename_categoriasdecredor_cargosfuncoes_and_more.py - Cargo system
- 0026_statuschoicessuprimentodefundos_suprimentodefundos_and_more.py - **Suprimento introduction**
- 0032_processo_arquivo_final.py - Final document archive
- 0035_notafiscal_atestada_alter_notafiscal_fiscal_contrato.py - Fiscal attestation
- 0041_historicaldocumentoauxilio_historicaldocumentodiaria_and_more.py - **History tracking added**

#### Phase 3: Advanced Features (0041-0083)
- 0046_rename_notafiscal_to_documentofiscal.py - **Major rename (NotaFiscal → DocumentoFiscal)**
- 0050_add_reinf_fields.py - REINF compliance
- 0053_add_rbac_permissions.py - **Permission system**
- 0062_add_devolucao_model.py - Fund return feature
- 0068_add_autentique_fields_to_diaria.py - **Digital signature support**
- 0072_add_reuniao_conselho.py - Council meeting model
- 0073_add_assinatura_autentique_and_remove_diaria_fields.py - Signature refinement
- 0075_refactor_tipos_documento_unique_constraint.py - Document type constraints
- 0080_contingencia_workflow_stages_and_contadora_review.py - **Contingency workflow**
- 0082_rename_boleto_bancario.py - **Final naming**: Boleto_Bancario

#### Merge Conflicts Resolved
- 0055_merge_20260318_0017.py
- 0059_merge_20260318_1904.py
- 0066_merge_20260321_1810.py
- 0066_merge_20260321_1811.py
- 0067_merge_20260322_2315.py

#### Key Schema Events
```
CRITICAL DEPENDENCIES:
├── Processo (core)
│   ├── depends: Credor, ContasBancarias
│   └── links: DocumentoFiscal, DocumentoOrcamentario, Diaria, SuprimentoDeFundos, etc.
├── DocumentoFiscal
│   ├── depends: Processo, Credor (emitente)
│   └── constraint: UNIQUE(processo, numero_nota_fiscal, serie_nota_fiscal)
├── SuprimentoDeFundos
│   ├── depends: Processo, Credor (suprido, PF only)
│   └── closure: requires data_retorno before finalization
├── Verba entities (Diaria, Jeton, Reembolso, Auxilio)
│   ├── depend: Processo, Credor (beneficiario, PF)
│   └── linked: DocumentoXxx per type (DespesaSuprimento is special case)
└── Audit Trail
    ├── HistoricalRecords on all core entities
    └── RegistroAcessoArquivo for file access tracking
```

---

## 6️⃣ SERVICES STRUCTURE (processos/services/)

**Organization:** Service layer for business logic isolation

```
processos/services/
├── __init__.py
├── fiscal/
│   ├── __init__.py
│   └── reinf.py                 [REINF XML generation & export]
├── fluxo/
│   ├── __init__.py
│   ├── documentos.py            [Document handling service]
│   └── errors.py                [Flow-specific exceptions]
├── integracoes/
│   ├── __init__.py
│   └── autentique.py            [Autentique API integration]
├── shared/
│   ├── __init__.py
│   ├── documentos.py            [Common document operations]
│   └── errors.py                [Shared exception classes]
└── verbas/
    ├── __init__.py
    └── diarias/
        ├── __init__.py
        └── documentos.py        [Diária document handling]
```

**Services Count:** 14 files

---

## 7️⃣ UTILITIES STRUCTURE (processos/utils/)

**Organization:** Support utilities for common tasks

```
processos/utils/
├── __init__.py
├── cadastros_import.py          [Credor bulk import logic]
├── csv_common.py                [CSV parsing utilities]
├── fluxo/
│   ├── __init__.py
│   └── contas.py                [Account utilities]
├── shared/
│   ├── __init__.py
│   ├── errors.py                [Exception hierarchy]
│   ├── pdf_tools.py             [PDF manipulation]
│   ├── relatorios.py            [Report generation helpers]
│   └── text_tools.py            [String/text processing]
└── verbas/
    ├── __init__.py
    └── diarias/
        ├── __init__.py
        ├── errors.py            [Diária-specific exceptions]
        ├── importacao.py        [Bulk diária import]
        └── siscac.py            [SISCAC integration & sync]
```

**Utilities Count:** 15 files

---

## 8️⃣ MANAGEMENT COMMANDS (processos/management/commands/)

**Organization:** Django management commands for dev/admin tasks

```
processos/management/commands/
├── __init__.py
├── create_sample_data.py        [Fake data generator for testing]
├── setup_baselines.py           [Initialize base data (status catalogs, etc.)]
└── setup_headstart.py           [Headstart catalogos + grupos/permissoes]
```

**Commands Count:** 3 active commands

---

## 9️⃣ TESTS STRUCTURE (processos/tests/)

**Organization:** Unit, integration, and functional tests

```
processos/tests/
├── __init__.py
├── test_app_segmentation_bootstrap.py           [App segmentation validation]
├── test_csv_import_merge_compat.py              [CSV import compatibility]
├── test_document_workflow_service.py            [Document service workflows]
├── test_fuzzing.py                             [Fuzz testing for robustness]
├── test_matching_primitives.py                 [Matching algorithm tests]
├── test_matching_strategies.py                 [Strategy pattern tests]
├── test_rbac.py                                [Permission system tests]
├── test_turnpike.py                            [State machine transition tests]
└── test_verbas_views_split.py                  [Verba view split validation]
```

**Tests Count:** 10 files

---

## 🔟 CROSS-DOMAIN DEPENDENCIES

### Dependency Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                          PROCESSOS APP                          │
├─────────────────────────────────────────────────────────────────┤
│  Processo (FLUXO) [Core Hub]                                    │
│  ├── References: Credor (CADASTROS)                             │
│  ├── References: DocumentoFiscal (FISCAL)                       │
│  ├── References: Diaria, Jeton, Reembolso, Auxilio (VERBAS)    │
│  └── References: SuprimentoDeFundos (SUPRIMENTOS)              │
│                                                                  │
│  DocumentoFiscal (FISCAL)                                        │
│  ├── Foreign Key: Processo                                      │
│  ├── Foreign Key: Credor (emitente)                            │
│  ├── Foreign Key: User (fiscal_contrato)                        │
│  └── Related: RetencaoImposto, CodigosImposto                   │
│                                                                  │
│  Verbas (DIARIA, JETON, REEMBOLSO, AUXILIO)                    │
│  ├── Foreign Key: Processo                                      │
│  ├── Foreign Key: Credor (beneficiario, PF only)              │
│  ├── Related: DocumentoDiaria, DocumentoJeton, etc.            │
│  └── Optional: ReuniaoConselho (Jeton)                         │
│                                                                  │
│  SuprimentoDeFundos (SUPRIMENTOS)                               │
│  ├── Foreign Key: Processo                                      │
│  ├── Foreign Key: Credor (suprido, PF only)                   │
│  ├── Related: DespesaSuprimento (expenses)                     │
│  └── Related: DocumentoSuprimentoDeFundos (docs)               │
│                                                                  │
│  Credor (CADASTROS) [Master Entity]                            │
│  ├── Foreign Key: ContasBancarias                               │
│  ├── Foreign Key: CargosFuncoes                                │
│  └── Reverse: Used in 6+ models                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Domain Isolation Patterns

| Feature | Domain | Dependencies | Purpose |
|---------|--------|--------------|---------|
| Payment Flow | Fluxo | Processo, DocumentoFiscal, Pendencia | Core workflow |
| Invoice Management | Fiscal | Processo, Credor (emitente), RetencaoImposto | Tax compliance |
| Allowance Handling | Verbas | Processo, Credor (beneficiario), CargosFuncoes | Employee benefits |
| Petty Cash | Suprimentos | Processo, Credor (suprido), DespesaSuprimento | Advance funds |
| Master Data | Cadastros | Credor, ContasBancarias, CargosFuncoes | Entity registry |

---

## 🔗 CRITICAL MIGRATION CHAINS

### Dependency Order (Safe Rollback/Forward)

```
Foundation (Must run first):
└─ 0001: Initial schema
   └─ 0006: Catalogs (Status, FormasPagamento, TiposDocumento)
      └─ 0010: Master entities (CargosFuncoes, Credor, ContasBancarias)
         ├─ 0021: Credor refinement (grupo system)
         └─ 0026: SuprimentoDeFundos introduction ✓
            └─ 0041: History tracking for document types ✓
               ├─ 0046: NotaFiscal → DocumentoFiscal rename
               ├─ 0050: REINF fields added
               └─ 0053: RBAC permissions model

Advanced Features:
├─ 0062: Devolucao (fund returns)
├─ 0068-0073: Autentique integration (signatures)
├─ 0072-0073: ReuniaoConselho & AssinaturaAutentique
├─ 0080: Contingencia workflow
└─ 0082: Boleto_Bancario → Boleto_Bancario rename
   └─ 0083: Final schema (criado_em removed from DocumentoOrcamentario)
```

### Breaking Changes in History

1. **0046**: `NotaFiscal` → `DocumentoFiscal` (table renamed, FK integrity preserved)
2. **0082**: `Boleto_Bancario` → `Boleto_Bancario` (semantic rename)
3. **0041**: Major addition of `HistoricalRecords` on all document types
4. **0053**: Permission system added (new Permission model)
5. **0080**: Contingency workflow stages refined

---

## 📋 FILE INVENTORY SUMMARY

```json
{
  "models": {
    "total_files": 5,
    "total_classes": 37,
    "total_lines": 1779,
    "by_domain": {
      "fluxo": 10,
      "fiscal": 5,
      "verbas": 12,
      "suprimentos": 4,
      "cadastros": 6
    }
  },
  "views": {
    "total_files": 126,
    "by_domain": {
      "fluxo": 82,
      "verbas": 26,
      "suprimentos": 8,
      "sistemas_auxiliares": 18,
      "fiscal": 2,
      "cadastros": 1,
      "other": 11
    }
  },
  "forms": {
    "total_file": 1,
    "total_classes": "12+",
    "organized_by": "domain"
  },
  "filters": {
    "total_file": 1,
    "total_classes": 14,
    "base_class": "BaseStyledFilterSet"
  },
  "migrations": {
    "total_files": 88,
    "latest": 83,
    "critical_renames": 3
  },
  "services": {
    "total_files": 14,
    "by_domain": {
      "fiscal": 1,
      "fluxo": 2,
      "integracoes": 1,
      "shared": 2,
      "verbas": 1
    }
  },
  "utilities": {
    "total_files": 15,
    "by_domain": {
      "fluxo": 1,
      "shared": 4,
      "verbas": 3,
      "root": 2
    }
  },
  "management": {
    "total_files": 3,
    "types": ["data_generation", "baseline_setup", "cargo_initialization"]
  },
  "tests": {
    "total_files": 10,
    "focus_areas": ["segmentation", "imports", "workflows", "rbac", "state_machine"]
  },
  "grand_total": {
    "python_files": 200,
    "lines_of_code": "~15,000+"
  }
}
```

---

## 🎯 ARCHITECTURE INSIGHTS

### Strengths
✅ **Clear domain segregation** — Models organized by business domain (fluxo, fiscal, verbas, suprimentos, cadastros)  
✅ **Comprehensive audit trail** — Full history tracking on all core entities via `HistoricalRecords()`  
✅ **Tight state machine** — Turnpike pattern prevents invalid transitions  
✅ **Multi-stage workflow** — Payment lifecycle split into pre-, payment, and post-payment stages  
✅ **External integrations** — SISCAC, Autentique, and REINF/EFD support built-in  
✅ **Flexible document handling** — Per-verba-type document models with shared base  

### Considerations
⚠️ **Single monolithic forms.py** — 350+ lines could be split by domain  
⚠️ **126 view files** — Deeply nested; consider flattening some modules  
⚠️ **Migration chain complexity** — 88 migrations with 3 major renames; careful orchestration needed  
⚠️ **Generic document relationships** — `GenericRelation` for AssinaturaAutentique adds flexibility but complexity  

---

## 📚 REFERENCES

- **Model Architecture**: `processos/models/segments/` (5 domain files)
- **View Orchestration**: `processos/views/fluxo/` (82 files, main workflow)
- **Business Logic**: `processos/services/` (14 utility modules)
- **Data Layer**: `processos/migrations/` (88 migration files)
- **Testing**: `processos/tests/` (10 test files)

---

**Document Generated:** 2026-04-08 | **Processos App v1.0** | **Status:** Production-Ready
