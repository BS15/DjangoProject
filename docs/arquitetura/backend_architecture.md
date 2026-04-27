# Arquitetura de Backend: Domínios Isolados e Dependências One-Way

## Por que o `processos` foi shattered

Historicamente, o sistema era construído como um único aplicativo Django monolítico chamado `processos`. Este design criou problemas:

1. **Acoplamento espaguete:** toda lógica de pagamentos, retenções, verbas e suprimentos vivia no mesmo app
2. **Ciclos de import:** utilitários importavam modelos que importavam validators que importavam utils
3. **Falta de boundary:** era impossível entender "isto é responsabilidade de quem?"
4. **Testes frágeis:** mudar uma coisa quebrava testes não relacionados

A solução foi **quebrar o monolito** em domínios isolados, cada um com responsabilidade clara.

## Arquitetura modular: Os cinco domínios

O PaGé é organizado em cinco apps Django semi-autônomos:

```
DjangoProject/
├── fluxo/                  # Core: máquina de estado, transições, auditoria
├── verbas_indenizatorias/  # Diárias, Jetons, Reembolsos, etc
├── suprimentos/            # Suprimento de fundos
├── fiscal/                 # NF-e, retenciones, EFD-Reinf
├── credores/               # Cadastro e dados mestres de fornecedores
├── commons/                # Utilitários compartilhados, PDF, assinaturas
└── pagamentos/             # Legacy app (em deprecação gradual)
```

### `fluxo/` — O Coração

Contém:
- **Modelos centrais:** `ProcessoDePagamento`, `ContaAReceber`, `DocumentoDePagamento`, [Empenho](/negocio/glossario_conselho.md#empenho), [Liquidação](/negocio/glossario_conselho.md#liquidacao), [Pagamento](/negocio/glossario_conselho.md#lancamento-bancario)
- **Máquina de estado:** transições bem definidas (A EMPENHAR → AGUARDANDO LIQUIDAÇÃO → A PAGAR → PAGO, etc)
- **Auditoria:** integração com `django-simple-history`
- **Validadores de domínio:** regras que aplicações satélites consultam

O fluxo é o coração do sistema. **Toda** operação passa por ele.

### `verbas_indenizatorias/`, `suprimentos/` — Aplicações satélites

Contêm:
- **Modelos específicos:** [Diária](/negocio/glossario_conselho.md#diaria), [Jeton](/negocio/glossario_conselho.md#jeton), [Suprimento de Fundos](/negocio/glossario_conselho.md#suprimento-de-fundos), etc
- **Views isoladas:** estrutura [Manager-Worker](/arquitetura/manager_worker.md) própria
- **Lógica de negócio própria:** regras de elegibilidade, cálculos, transições

Estas apps consomem `fluxo/` mas são independentes entre si.

### `fiscal/` — Integração com órgãos externos

Contém:
- **Sincronização de NF-e:** integração com sistema fiscal
- **[Retenções](/negocio/glossario_conselho.md#retencao-de-imposto):** cálculo de impostos e repasse
- **EFD-Reinf:** geração de escrituração fiscal

### `credores/` — Dados mestres

Contém:
- **Cadastro de fornecedores**
- **Dados fiscais:** CNPJ, inscrição estadual, tipo de pessoa
- **Contas correntes:** dados de TED

### `commons/` — Infraestrutura compartilhada

Contém:
- **Utilitários de PDF:** geração, extração, merge
- **Serviços de assinatura:** integração com Autentique
- **Storage e arquivo:** upload/download seguro
- **Ferramentas de texto:** normalização, formatação

## Regra de Dependências: One-Way

**Dependências permitidas:**

```
verbas_indenizatorias ──┐
suprimentos ────────────┼──> fluxo (core)
fiscal ─────────────────┤
credores ───────────────┴

pagamentos (legacy) ────> fluxo

Todos: commons (infraestrutura)
```

**Dependências proibidas:**

- ❌ `fluxo/` importa de `verbas_indenizatorias/`, `suprimentos/`, `fiscal/` (ciclo!)
- ❌ `verbas_indenizatorias/` importa de `suprimentos/` (cruzamento)
- ❌ `credores/` importa de `pagamentos/`

### Por que one-way?

1. **Evita ciclos:** `fluxo` não "conhece" apps que o usam
2. **Facilita testes:** você pode testar `fluxo/` sem provisionar toda a infraestrutura de aplicações satélites
3. **Clareza de boundary:** "satélite depende do core, nunca o contrário"

## Implementação de shared logic sem breaking one-way

Se você precisa de lógica compartilhada entre satélites sem inserir no core:

✅ **Correto:** Coloque em `commons/shared/` (infrastructure)
```python
# commons/shared/document_services.py
def anexar_documento_generico(modelo, arquivo):
    """Usado por diarias, suprimentos, fiscal, etc"""
    pass
```

❌ **Errado:** Coloque em `fluxo/` (isso vira "core")
```python
# fluxo/services/document_services.py — NÃO FAÇA ISTO
def anexar_documento_generico(...):
    pass
```

## Import chains e como evitar ciclos

Monitorar cycles com:
```bash
python manage.py check
```

Se vir:
```
SystemCheckError: System check identified some issues:
E001 … circular import detected between fluxo and verbas_indenizatorias
```

**Estratégia de resolução:**

1. Procure imports em nível de módulo (`from ... import ...` no topo do arquivo)
2. Mova-os para imports locais (dentro de funções)
3. Exemplo:

```python
# models.py — ❌ ERRADO
from ..services.transicoes import transicion_pode_avancar

class ProcessoDePagamento(models.Model):
    def avanca(self):
        transicion_pode_avancar(self)

# models.py — ✅ CORRETO
class ProcessoDePagamento(models.Model):
    def avanca(self):
        from ..services.transicoes import transicion_pode_avancar
        transicion_pode_avancar(self)
```

## Estrutura recomendada por app satélite

Cada app que depende de `fluxo/` deveria ter:

```
meu_app/
├── models.py           # Modelos específicos
├── apps.py
├── forms.py
├── filters.py
├── admin.py
├── migrations/
├── views/              # Manager-Worker structure
│   ├── modulo1/
│   │   ├── panels.py
│   │   ├── actions.py
│   │   ├── forms.py
│   │   ├── helpers.py
│   │   └── services/
│   └── modulo2/
│       └── ...
├── services/           # Serviços de negócio
│   ├── criacao_service.py
│   ├── transicoes_service.py
│   └── validacoes_service.py
├── migrations/
├── templates/
│   └── meu_app/
└── tests/
    └── test_views.py
```

## Checklist: Validando isolamento

Antes de submeter PR:

- ✅ `fluxo/` não importa do seu app
- ✅ Seu app importa apenas de `fluxo/`, `commons/`, `credores/`
- ✅ Circulares detectados? Use imports locais
- ✅ `python manage.py check` passa
- ✅ Urls estão em `urlconf/` centralizado, não em app
