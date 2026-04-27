# Code Generation: Pattern Matching First

Antes de escrever **qualquer** novo feature do zero, você DEVE procurar por uma feature análoga já existente no codebase e **replicar seu padrão exato**.

Para padrões de views, consulte [Padrão Manager-Worker](manager_worker.md), [Interface Hub-and-Spoke](hub_spoke.md) e [Template Tiers](template_tiers.md).

## Por que isto importa

1. **Consistência estrutural** — usuários e novos desenvolvedores reconhecem a forma do código imediatamente
2. **Evita divergência idiomática** — sem padrão matching, cada desenvolvedor inventa sua própria organização
3. **Reduz tempo de review** — reviewers focam em lógica de negócio, não discutem organização de arquivos

## Workflow prático

### Cenário: Você precisa construir um endpoint para "Reembolsos" indenizatérios

**Passo 1: Procure análogo**
- Você sabe que "[Diárias](/negocio/glossario_conselho.md#diaria)" e "[Jetons](/negocio/glossario_conselho.md#jeton)" são indenizações similares
- Você sabe que ambas têm fluxos bem definidos

**Passo 2: Copie estrutura**

Examine:
```
verbas_indenizatorias/views/diarias/
├── __init__.py
├── panels.py
├── actions.py
├── forms.py
├── helpers.py
└── services/
    ├── __init__.py
    ├── criacao_service.py
    └── transicoes_service.py
```

Replique exatamente em:
```
verbas_indenizatorias/views/reembolsos/
├── __init__.py        # Copiar imports pattern
├── panels.py          # Copiar GET pattern
├── actions.py         # Copiar POST pattern
├── forms.py           # Copiar formulários
├── helpers.py         # Copiar helpers pattern
└── services/
    ├── __init__.py
    ├── criacao_service.py
    └── transicoes_service.py
```

**Passo 3: Replica include patterns**

Examine como `diarias/` é importado em `verbas_indenizatorias/urls.py`:

```python
from .views.diarias import panels as diarias_panels
from .views.diarias import actions as diarias_actions
```

Replique para `reembolsos/`:

```python
from .views.reembolsos import panels as reembolsos_panels
from .views.reembolsos import actions as reembolsos_actions
```

**Passo 4: Copia padrão de naming de URLs**

Se Diárias usa:
```python
path('diaria/<int:id>/editar/', ...)
path('diaria/<int:id>/autorizar/', ...)
```

Reembolsos deve seguir:
```python
path('reembolso/<int:id>/editar/', ...)
path('reembolso/<int:id>/autorizar/', ...)
```

## Padrões estabelecidos para copiar

### 1. Views por domínio (Manager-Worker)

- `panels.py` — GET only, retorna context dict, renderiza template
- `actions.py` — POST only, valida form, chama service, redireciona
- `services/` — domain logic, transactions, business rules
- `forms.py` — Django Forms, validação de entrada
- `helpers.py` — utilitários privados da view

Referência detalhada: [Padrão Manager-Worker](manager_worker.md).

### 2. Templates e layouts

Sempre estenda um dos base layouts:
```django
{% extends "layouts/base_detail.html" %}
```

Guia completo de herança e contratos de layout: [Template Tiers](template_tiers.md).

Nunca escreva HTML standalone (layout/header/footer suas).

### 3. Modelos e migrações

Se criar novo modelo:
- Use `models.py` canônico do módulo
- Estenda `BaseModeloAuditado` ou similar existente
- Use verbose_name + verbose_name_plural idênticos ao histórico

## Validando pattern matching

Antes de submeter PR, valide:

- ✅ Estrutura de pastas é idêntica ao análogo
- ✅ Imports seguem convenção vizinha
- ✅ URLs seguem naming precedente
- ✅ Templates estendem base_* correto
- ✅ Serviços isolam lógica de views
- ✅ No templates renderizados em Actions
- ✅ Sem lógica de negócio em Panels

Se qualquer um destes falhar: retorne ao análogo e copie EXATAMENTE.

Para regras de estado, turnpikes e auditoria em fluxos financeiros, consulte [Domain Knowledge](domain_knowledge.md) e [Trilha de Auditoria](../governanca/trilha_auditoria.md).
