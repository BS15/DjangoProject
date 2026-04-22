# Guia de Contribuição

Obrigado por contribuir com o PaGé. Este guia define os padrões que todos os colaboradores devem seguir.

---

## Pré-requisitos

Consulte [docs/desenvolvedor/setup_ambiente.md](docs/desenvolvedor/setup_ambiente.md) para instruções completas de configuração do ambiente (Docker ou local).

Resumo rápido:

```bash
cp .env.example .env
# Preencher variáveis obrigatórias no .env
docker compose up --build
```

---

## Estratégia de Branches

- O branch principal é `main`.
- Crie branches de feature a partir de `main` usando o padrão: `feature/<descricao-curta>`.
- Correções de bug: `fix/<descricao-curta>`.
- Documentação: `docs/<descricao-curta>`.

---

## Antes de Abrir um PR

Execute as verificações abaixo e certifique-se de que passam:

```bash
# Checks do Django (detecta erros de configuração, modelos e URLs)
python manage.py check

# Testes automatizados
python manage.py test
```

---

## Padrão de PR

- **Título:** curto e descritivo em português (`Adiciona endpoint de criação de reembolso`).
- **Descrição:** descrever o que muda, por que muda e como testar manualmente.
- **Tamanho:** prefira PRs focados em uma única responsabilidade.
- Pelo menos um revisor antes do merge.

---

## Padrões de Código

Documentação completa em [docs/desenvolvedor/padroes_codigo.md](docs/desenvolvedor/padroes_codigo.md). Resumo dos pontos críticos:

### Separação Manager-Worker

| Arquivo | Responsabilidade |
|---|---|
| `panels.py` | Apenas `GET`. Compila contexto e renderiza templates. Nunca muta o banco. |
| `actions.py` | Apenas `POST`. Valida, chama services e retorna `HttpResponseRedirect`. Nunca renderiza template. |
| `services/` | Toda mutação de banco, transição de estado e lógica de negócio complexa. |

### Templates

Sempre estender o layout Tier-2 adequado — nunca escrever HTML boilerplate avulso:

```django
{% extends "layouts/base_form.html" %}
{% extends "layouts/base_list.html" %}
{% extends "layouts/base_detail.html" %}
{% extends "layouts/base_review.html" %}
```

### Autorização

```python
# CORRETO
@permission_required('app_label.codename', raise_exception=True)

# NUNCA usar
@login_required
```

### Imutabilidade de Dados

Não deletar registros. Use modelos `Contingência` ou `Devolução` para exceções de fluxo. Toda mutação relevante é auditada via `django-simple-history`.

### Aritmética Financeira

```python
# CORRETO
from decimal import Decimal
valor = Decimal('100.50')

# NUNCA usar float para valores monetários
```

### Padrão "Pattern Match First"

Antes de criar qualquer módulo novo, localize um módulo análogo no codebase e replique exatamente a mesma hierarquia de arquivos, convenção de nomenclatura e fluxo de imports. Exemplo: ao implementar "Reembolsos", estudar "Diárias" antes de escrever qualquer linha.

---

## Clean Slate Protocol (Pré-V1)

Durante a fase pré-V1, mudanças de schema incompatíveis são tratadas com reinicialização do banco ao invés de migrações complexas. Consulte [docs/desenvolvedor/setup_ambiente.md](docs/desenvolvedor/setup_ambiente.md) para o procedimento.

Registre toda mudança significativa de schema no [CHANGELOG.md](CHANGELOG.md).
