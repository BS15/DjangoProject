# Template Tiers: As Quatro Camadas Base

O PaGé utiliza herança de templates em quatro camadas base, garantindo consistência visual e funcional em toda a interface.

Nunca escreva HTML standalone. **Sempre estenda** uma destas camadas.
Para o padrão de views associado, consulte [Manager-Worker](manager_worker.md) e [Hub-and-Spoke](hub_spoke.md).
## Arquitetura

```
                     base.html
                        │
        ┌───────────────┼───────────────┬────────────────┐
        │               │               │                │
   base_list.html  base_detail.html  base_form.html  base_review.html
        │               │               │                │
        ▼               ▼               ▼                ▼
   Listagens      Painéis de       Formulários      Páginas de
   de Registros   Comando (Hubs)   de Entrada       Revisão/Aprovação
```

## Tier 1: `base.html`

A camada raiz. Contém:
- Estrutura HTML global (doctype, head, body)
- Navbar principal
- Menu lateral (sidebar)
- Scripts e CSS compartilhados
- Blocos base para conteúdo principal

**Não estenda diretamente.** Sempre estenda uma das camadas Tier 2.

## Tier 2: Quatro camadas especializadas

### 1. `base_list.html`

Para exibir coleções de registros em formato tabular ou de grid.

**Características:**
- Tabela paginada (padrão: 25 linhas/página)
- Barra de filtros acima da tabela
- Ações em massa (checkboxes)
- Botão "Novo" no topo direito
- Sem formulários inline; links para detalhe ou spoke

**Usado por:**
- Listagem de Processos de Pagamento
- Listagem de Diárias
- Listagem de Suprimentos
- Listagem de Notas Fiscais

**Exemplo:**

```django
{% extends "layouts/base_list.html" %}

{% block title %}Processos de Pagamento{% endblock %}

{% block filters %}
  <!-- filtros_form.html incluso aqui -->
{% endblock %}

{% block table %}
  <!-- tabela de processos -->
{% endblock %}
```

### 2. `base_detail.html`

Para exibir detalhes completos de um registro (o "Hub").

**Características:**
- Cabeçalho com identificação do registro
- Status badge + timestamp
- Seções colapsáveis (abas)
- Histórico de auditoria (`django-simple-history`)
- Botões de ação linkando para spokes (não formulários inline)
- Sem campos de edição; tudo é read-only

**Usado por:**
- Detalhe de Processo de Pagamento
- Detalhe de Diária
- Detalhe de Suprimento
- Painel operacional de vendas, compras, etc

**Exemplo:**

```django
{% extends "layouts/base_detail.html" %}

{% block title %}Processo {{ processo.id }}{% endblock %}

{% block header_info %}
  <h1>Processo #{{ processo.id }}</h1>
  <span class="badge badge-{{ processo.status|lower }}">{{ processo.status }}</span>
{% endblock %}

{% block sections %}
  <div class="tab-content">
    <section>
      <h3>Detalhes Financeiros</h3>
      <dl>
        <dt>Valor:</dt>
        <dd>R$ {{ processo.valor|default:"—" }}</dd>
      </dl>
    </section>
  </div>
{% endblock %}

{% block actions %}
  <a href="{% url 'avancar_para_pagamento' objeto.id %}" class="btn btn-primary">Avançar</a>
{% endblock %}
```

### 3. `base_form.html`

Para entrada de dados via formulário (os "Spokes").

**Características:**
- Formulário simples (um objetivo)
- Validação de entrada (regras Django Form)
- jQuery auto-masking para:
  - Valores monetários (R$)
  - CPF/CNPJ
  - Telefone
  - Data
- Botão `Salvar` e `Cancelar`
- Mensagens de erro amigáveis
- Sem seções colapsáveis (manter simples)

**Usado por:**
- Criar Diária
- Revisar comprovantes de suprimento
- Registrar Nota Fiscal
- Aprovar empenho
- Transferir verbas

**Exemplo:**

```django
{% extends "layouts/base_form.html" %}

{% block title %}Registrar Nota Fiscal{% endblock %}

{% block form %}
  <form method="post" class="form">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit" class="btn btn-primary">Salvar</button>
    <a href="{{ request.META.HTTP_REFERER }}" class="btn btn-secondary">Cancelar</a>
  </form>
{% endblock %}
```

O `base_form.html` inclui automaticamente:
- Bootstrap 5 styling
- Font Awesome icons
- jQuery Mask plugin (para R$, CPF, CNPJ, datas)

### 4. `base_review.html`

Para páginas de revisão, assinatura ou aprovação formal.

**Características:**
- Layout lado-a-lado: esquerda mostra dados, direita mostra confirmação
- Checklist de validações (turnpikes)
- Seção de assinatura eletrônica (se aplicável)
- Histórico de tentativas anteriores (se houver falha)
- Sem edição; dados são read-only
- Botões de aprovação + rejeição

**Usado por:**
- Validação final de empenho
- Assinatura de liquidação
- Aprovação de prestação de contas
- Revisão de devolução de fundos

**Exemplo:**

```django
{% extends "layouts/base_review.html" %}

{% block title %}Revisar Empenho{% endblock %}

{% block data %}
  <section class="review-data">
    <h3>Dados do Empenho</h3>
    <dl>
      <dt>Processo:</dt>
      <dd>#{{ objeto.processo.id }}</dd>
    </dl>
  </section>
{% endblock %}

{% block validations %}
  <section class="review-checklist">
    {% for turnpike, status in turnpikes.items %}
      <label>
        <input type="checkbox" disabled {% if status %}checked{% endif %}>
        {{ turnpike }}
      </label>
    {% endfor %}
  </section>
{% endblock %}

{% block signature %}
  {% include "support/signature_widget.html" with assinatura_id=signature.id %}
{% endblock %}

{% block actions %}
  <button form="approve-form" class="btn btn-success">Aprovar</button>
  <button form="reject-form" class="btn btn-danger">Rejeitar</button>
{% endblock %}
```

## Estrutura de herança visual

```
User Interface
     │
     ▼
+─────────────────────+
│   Navigation Bar    │  (Navbar incluso em base.html)
+─────────────────────+
│ │                   │
│ │  Sidebar          │  (Sidebar incluso em base.html)
│ │                   │
│ └─────────────────────────────────────┐
│                                       │
│         Main Content Area             │
│   (Renderizado pela Tier 2)          │
│                                       │
└───────────────────────────────────────┘
```

## Regras imutáveis

1. **Nunca escreva `{% extends "base.html" %}` diretamente.** Sempre escolha uma Tier 2.

2. **Um template por responsabilidade:**
   - Listar → `base_list.html`
   - Detalhe (read-only) → `base_detail.html`
   - Editar/Criar → `base_form.html`
   - Revisar/Assinar → `base_review.html`

3. **Sem lógica de negócio em templates.** Se precisar de condicional complexo, compute no Panel/Action e passe como context.

4. **Reutilização via `{% include %}`:**
   ```django
   {% extends "layouts/base_detail.html" %}
   {% block sections %}
     {% include "shared/tabela_documentos.html" %}
     {% include "shared/tabela_assinaturas.html" %}
   {% endblock %}
   ```

5. **CSS classes padronizadas:**
   - `.btn-primary` — ação principal (Salvar, Aprovar)
   - `.btn-secondary` — ação alternativa (Cancelar)
   - `.btn-danger` — ação destrutiva (Rejeitar, Deletar)
   - `.badge-success`, `.badge-warning`, `.badge-danger` — status

## Validação de template

Antes de submeter PR:

- ✅ Template estende exatamente uma das quatro Tier 2
- ✅ Sem `{% extends "base.html" %}`
- ✅ Sem lógica complexa em template (if/for excessivos)
- ✅ CSS classes seguem convenção Bootstrap 5
- ✅ Imagens/ícones usam Font Awesome ou estão em `/static/`
