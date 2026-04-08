# Next Steps — Fase 2: Split de Models em Ondas

**Objetivo**: Migrar modelos para novos apps (fluxo, verbas_indenizatorias, suprimentos) sem quebrar RBAC, auditoria ou navegação.

---

## Resumo Executivo

### Estado Atual (Fim de Fase 1):
- ✓ Baseline de 172 testes confirmado
- ✓ URLs e permissões congeladas + testadas
- ✓ Domínios formalizados em 6 grupos
- ✓ Zero quebra de compatibilidade de imports

### Próximas Ações (Priorizado):

#### Fase 2a: Setup de Apps Novos (1-2 dias)
1. Criar `fluxo`, `verbas_indenizatorias`, `suprimentos` via `startapp`
2. Adicionar a `INSTALLED_APPS` em `settings.py`
3. Criar estrutura inicial (`models.py`, `admin.py`, `apps.py`)
4. Rodar `manage.py check` + testes (devem permanecer estáveis)

#### Fase 2b: Onda 1 — Verbas (2-3 dias)
1. Copiar modelos de verbas de `processos/models/segments/_verbas_models.py` → `verbas_indenizatorias/models.py`
2. Criar migração inicial de verbas
3. Data migration para migrar `django_content_type` e `auth_permission`
4. Atualizar imports em views/services/forms/filters
5. Atualizar decorators `@permission_required` para novo `app_label`
6. Rodar testes de contrato congelado + suite completa

#### Fase 2c: Onda 2 — Suprimentos (2-3 dias)
Idem Onda 1 para `suprimentos`

#### Fase 2d: Onda 3 — Fluxo (3-4 dias)
Idem Onda 1 para `fluxo` (mais complexo por ser nuclear)

#### Fase 2e: Integração & Hardening (2-3 dias)
1. Remover compatibilidade shims (manter apenas se necessário para staging)
2. Validar fluxo end-to-end (A EMPENHAR → ARQUIVADO)
3. Validar histórico de auditoria
4. Testar rollback de dados

---

## Checklist Pré-Fase 2

Antes de começar a mover modelos:

- [ ] Ler [`PHASE1_DOMAINS_ANALYSIS.md`](PHASE1_DOMAINS_ANALYSIS.md)
- [ ] Ler [`PHASE1_FROZEN_CONTRACTS.md`](PHASE1_FROZEN_CONTRACTS.md)
- [ ] Verificar baseline: `python manage.py test -- -v 1` (172 PASS)
- [ ] Backup de banco de dados (local + staging):
  ```bash
  # SQLite local
  cp db.sqlite3 db.sqlite3.backup.phase1
  
  # PostgreSQL staging (comando do DBA)
  pg_dump -h <host> -U <user> <dbname> > fase2_baseline.sql
  ```
- [ ] Branch de feature: `git checkout -b feature/split-models-phase2`

---

## Script de Inicialização Fase 2a (Apps Novos)

```bash
#!/bin/bash
# 1. Criar apps
python manage.py startapp fluxo
python manage.py startapp verbas_indenizatorias
python manage.py startapp suprimentos

# 2. Estrutura mínima (criar manualmente ou via scaffold)
touch fluxo/models.py
touch fluxo/admin.py
touch fluxo/managers.py
# ... etc

# 3. Validação
python manage.py check
python manage.py test processos.tests.test_frozen_contracts -v 2

echo "✓ Phase 2a ready. Proceed to Onda 1."
```

---

## Exemplo de Migração Onda 1 (Verbas)

### 1. Setup do App

**`verbas_indenizatorias/apps.py`:**
```python
from django.apps import AppConfig

class VerbaInduzatoriaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'verbas_indenizatorias'
    verbose_name = 'Verbas Indenizatórias'
```

**`verbas_indenizatorias/models.py`:**
```python
# Copiar todo conteúdo de processos/models/segments/_verbas_models.py
# Ajustar FKs para Processo se forem string references
```

### 2. Migração Inicial

```bash
python manage.py makemigrations verbas_indenizatorias
python manage.py migrate verbas_indenizatorias
```

### 3. Data Migration para ContentType + Permission

```bash
python manage.py makemigrations processos --empty migrate_verbas_contenttype --name=0001_migrate_verbas_contenttype
```

**Dentro da data migration:**
```python
from django.db import migrations
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission

def migrate_ct_perms(apps, schema_editor):
    """Mover ContentType + Permissions de processos → verbas_indenizatorias."""
    old_ct = ContentType.objects.get(app_label='processos', model='diaria')
    new_ct = ContentType.objects.get(app_label='verbas_indenizatorias', model='diaria')
    
    # Atualizar permissions
    Permission.objects.filter(content_type=old_ct).update(content_type=new_ct)
    
    # Deletar old ContentType (cuidado!)
    old_ct.delete()

def reverse(apps, schema_editor):
    # Reverter se necessário
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('verbas_indenizatorias', '0001_initial'),
    ]
    
    operations = [
        migrations.RunPython(migrate_ct_perms, reverse),
    ]
```

### 4. Atualizar Imports

```bash
# Em processos/views/verbas/ e services/verbas/
# Mudar de:
from processos.models.segments._verbas_models import Diaria
# Para:
from verbas_indenizatorias.models import Diaria
```

### 5. Atualizar Decorators

```bash
# Em processos/views/verbas/processo/...]
# Mudar de:
@permission_required("processos.pode_visualizar_verbas")
# Para:
@permission_required("verbas_indenizatorias.pode_visualizar_verbas")
```

### 6. Validar

```bash
python manage.py check
python manage.py test processos.tests.test_frozen_contracts -v 2
# Expected: 17 PASS (URLs + perms sob novo app_label)
python manage.py test
# Expected: 172 PASS
```

---

## Estratégia de Rollback

Se algo quebrar em Fase 2:

```bash
# 1. Reverter última migração de dados
python manage.py migrate <app> <numero_anterior>

# 2. Reverter código
git checkout HEAD~1

# 3. Restaurar banco
# SQLite:
cp db.sqlite3.backup.phase1 db.sqlite3

# PostgreSQL:
psql -h <host> -U <user> <dbname> < fase2_baseline.sql  # em staging

# 4. Validar
python manage.py check
python manage.py test
```

---

## Pontos de Atenção

### 1. GenericForeignKey (AssinaturaAutentique)
- Usa `ContentType` dinamicamente
- **Deve continuar funcionando** pós-migração (resolve por app_label/model)
- Testar: Criar assinatura em novo app_label, verificar se resolve

### 2. SimpleHistory (Auditoria)
- Tabelas históricas (`historicaldiaria`, etc.) ficarão em app antigo temporariamente
- **Data migration pode ser complexa** — deixar para última hora se possível
- Opção: Aceitar que histórico antigo fica em `processos`, novo em novo app

### 3. Admin

Opções:
- **Opção A**: Manter admin unificado em `processos/admin.py` (mais simples)
- **Opção B**: Refatorar admin por app (mais limpo, mais work)

Recomendação: **Opção A para Fase 2** (fazer Opção B em Fase 3 se tempo permitir)

### 4. Related Names em FK

Se `Diaria.processo` tem `related_name='diarias'`, este continuará funcionando:
```python
processo.diarias.all()  # Continua ok mesmo após Diaria migrar de app
```

---

## Matriz de Testes por Onda

### Onda 1 (Verbas)

| Test | Esperado | Check |
|------|----------|-------|
| URL `painel_verbas` resolve | ✓ | `reverse('painel_verbas')` |
| Permission `pode_visualizar_verbas` existe | ✓ | `Permission.objects.get(codename=...)` |
| Diaria.objects.create() funciona | ✓ | `python manage.py shell` |
| Add/edit diária views funcionam | ✓ | Smoke test manual |
| Histórico de diária funciona | ✓ | Editar diária, verificar history |
| Suite de testes passa | 172 PASS | `python manage.py test` |

### Onda 2 & 3
Idem, substituindo "Verbas" → "Suprimentos" / "Fluxo"

---

## Tempo Estimado (Com Risco Buffered)

| Fase | Atividade | Estimado | Risco | Total |
|------|-----------|----------|-------|-------|
| 2a | Setup de apps | 4h | Baixo | 4h |
| 2b | Onda 1 (Verbas) | 2d | Médio | 3d |
| 2c | Onda 2 (Suprimentos) | 2d | Médio | 3d |
| 2d | Onda 3 (Fluxo) | 3d | Alto | 4d |
| 2e | Integração/hardening | 2d | Médio | 3d |
| **Total** | | | | **~2 semanas** |

---

## Leitura Recomendada Antes de Começar

1. [Django: Moving Models Between Apps](https://docs.djangoproject.com/en/stable/releases/1.7/#features-removed-in-1-7)
2. [django-simple-history: Migration Strategies](https://django-simple-history.readthedocs.io/)
3. [Django Data Migrations Best Practices](https://docs.djangoproject.com/en/stable/topics/migrations/#runpython)
4. Nossos artefatos: [`PHASE1_DOMAINS_ANALYSIS.md`](PHASE1_DOMAINS_ANALYSIS.md), [`PHASE1_FROZEN_CONTRACTS.md`](PHASE1_FROZEN_CONTRACTS.md)

---

## Contato e Escalation

- **Pergunta técnica sobre migração**: Revisar [`PHASE1_DOMAINS_ANALYSIS.md`](PHASE1_DOMAINS_ANALYSIS.md) seção 5
- **Erro em data migration**: Reverter, inspecionar, criar test unitário
- **Quebra de navegação**: Rodar `python manage.py test processos.tests.test_frozen_contracts`
- **Perda de histórico**: Não deletar tabelas históricas, usar data migration ao invés

---

**Próximo milestone**: Fase 2a (Setup) — **Pronto quando quiser começar!**

