# Domain Knowledge: Public Administration Compliance

O PaGé executa conformidade com rigorosas exigências de administração pública brasileira. Esta seção documenta os padrões arquiteturais que garantem legalidade, rastreabilidade e imutabilidade.

## 1. Máquina de Estado Rígida

[Processos financeiros](/negocio/glossario_conselho.md#processo) no setor público não evoluem "como querem". Seguem uma máquina de estado estrita, onde cada transição é permitida apenas sob certos pré-requisitos.

### Exemplo: Processo de Pagamento

```
A EMPENHAR
    ▼
AGUARDANDO LIQUIDAÇÃO
    ▼
A PAGAR - PENDENTE AUTORIZAÇÃO
    ▼
A PAGAR - PENDENTE ASSINATURA
    ▼
PAGO
    ▼
ARQUIVADO
```

Cada flecha é uma **transição validada** por regras de negócio.

### Transições permitidas

- De `A EMPENHAR` → `AGUARDANDO LIQUIDAÇÃO`: exige [Empenho](/negocio/glossario_conselho.md#empenho) + contrato + [Nota Fiscal](/negocio/glossario_conselho.md#nota-fiscal)
- De `AGUARDANDO LIQUIDAÇÃO` → `A PAGAR - PENDENTE AUTORIZAÇÃO`: exige [liquidação](/negocio/glossario_conselho.md#liquidacao) formal
- De `A PAGAR - PENDENTE AUTORIZAÇÃO` → `A PAGAR - PENDENTE ASSINATURA`: exige aprovação de líder
- De `A PAGAR - PENDENTE ASSINATURA` → `PAGO`: exige assinatura eletrônica válida
- De qualquer estado → `CANCELADO`: se cumpridas regras de devolução

### Implementação

Transições são orquestradas via `Services`:

```python
# verbas_indenizatorias/services/transicoes_service.py
def transicionar_diaria_para_prestacao(diaria: Diaria):
    """Passa diária de EMITIDA para PRESTACAO se pré-condições OK"""
    
    # 1. Validate preconditions (turnpikes)
    if not diaria.beneficiario.usuario:
        raise PrecondicaoNaoAtendida("Beneficiário sem usuário")
    
    # 2. Execute mutation
    with transaction.atomic():
        diaria.status = Diaria.Status.PRESTACAO
        diaria.data_status = now()
        diaria.save(update_fields=['status', 'data_status'])
        
        # 3. Emit audit event
        registrar_auditoria(
            usuario=request.user,
            acao="TRANSICIONAR_PARA_PRESTACAO",
            objeto=diaria,
            dados_antes={...},
            dados_depois={...}
        )
```

## 2. O Padrão Turnpike: Validações de Pré-Condição

Um **[Turnpike](/negocio/glossario_conselho.md#turnpike)** é uma validação que bloqueia uma transição até que todas as condições sejam atendidas. Sem documentação obrigatória = sem avanço.

### Exemplos de turnpikes

**Processo de Pagamento:**
- ✅ Existe empenho válido?
- ✅ Existe liquidação com nota fiscal?
- ✅ Valor liquidado ≤ valor empenho?
- ✅ Todos os documentos de comprovação foram juntados?
- ✅ Assinaturas eletrônicas recolhidas?

**Prestação de Contas de Diária:**
- ✅ Beneficiário anexou comprovantes (notas, recibos)?
- ✅ Valor devolvido + valor gasto = valor concedido?
- ✅ Documentos estão em PDF válido?

**Suprimento de Fundos:**
- ✅ Suprido juntou todas as notas fiscais?
- ✅ Valor total de despesas ≤ limite autorizado?
- ✅ Não há despesas duplicadas?

### Implementação

Turnpikes são validadores reutilizáveis:

```python
# commons/services/turnpike_validators.py

class TurnpikeValidator:
    """Base para validadores de pré-condição"""
    
    @staticmethod
    def validar_documentos_obrigatorios(processo, tipos_obrigatorios):
        """Verifica se todos os tipos de doc foram juntados"""
        anexados = set(processo.documentos.values_list('tipo', flat=True))
        faltantes = set(tipos_obrigatorios) - anexados
        
        if faltantes:
            raise TurnpikeNaoAtendido(
                f"Documentos faltantes: {', '.join(faltantes)}"
            )
        return True
    
    @staticmethod
    def validar_assinaturas_necessarias(documento):
        """Verifica se todas as assinaturas foram coletadas"""
        assinantes_necessarios = documento.definir_assinantes()
        assinantes_presentes = documento.assinaturas.filter(
            status=Assinatura.Status.ASSINADO
        ).count()
        
        if assinantes_presentes < len(assinantes_necessarios):
            raise TurnpikeNaoAtendido(
                f"Faltam {len(assinantes_necessarios) - assinantes_presentes} assinaturas"
            )
        return True
```

Antes de qualquer transição, o Service chama os Turnpikes:

```python
# Simples mas explícito
def avancar_processo(processo, usuario):
    from commons.services import TurnpikeValidator
    
    TurnpikeValidator.validar_documentos_obrigatorios(
        processo,
        tipos_obrigatorios=["EMPENHO", "NOTA_FISCAL"]
    )
    TurnpikeValidator.validar_assinaturas_necessarias(processo.assinatura)
    
    processo.status = ProcessoStatus.PRONTO_PARA_PAGAMENTO
    processo.save()
```

## 3. Imutabilidade & Auditoria

Dinheiro público é sagrado. Nenhum registro é jamais **deletado**. Alterações são **registradas** e rastreáveis.

### Never Delete: Use flags instead

❌ **Errado:**
```python
documento.delete()
```

✅ **Correto:**
```python
documento.data_revogacao = now()
documento.revogado_por = usuario
documento.save(update_fields=['data_revogacao', 'revogado_por'])
```

### Auditoria com `django-simple-history`

Toda alteração é rastreada automaticamente:

```python
from simple_history.models import HistoricalRecords

class Processo(models.Model):
    status = models.CharField(...)
    valor = models.DecimalField(...)
    history = HistoricalRecords()
```

Quando você faz:
```python
processo.valor = Decimal("5000.00")
processo.save()
```

Django-simple-history cria automaticamente um registro de histórico da entidade `Processo`:

```
| id  | valor     | status                                | changed_by | changed_at          |
|-----|-----------|---------------------------------------|------------|---------------------|
| 1   | 1000.00   | A EMPENHAR                            | user@...   | 2026-04-24 10:15:00 |
| 2   | 5000.00   | AGUARDANDO LIQUIDAÇÃO                 | admin@...  | 2026-04-24 11:30:00 |
```

### Exceções: Contingência & Devolução

Quando uma operação falha ou precisa ser "desfeita", não se deleta. Usa-se modelos de exceção:

```python
class ContingenciaDiaria(models.Model):
    """Quando uma diária autorizada é cancelada antes de ser paga"""
    diaria = ForeignKey(Diaria, on_delete=PROTECT)
    motivo = TextField()
    data_contingencia = DateTimeField(auto_now_add=True)
    autorizado_por = ForeignKey(User, on_delete=PROTECT)
    
class DevolucaoSuprimento(models.Model):
    """Quando um suprimento de fundos é devolvido antes de pago"""
    suprimento = ForeignKey(Suprimento, on_delete=PROTECT)
    valor_devolvido = DecimalField()
    data_devolucao = DateTimeField(auto_now_add=True)
    comprovante = FileField()
```

Fluxo:
1. Diária criada (status: EMITIDA)
2. Beneficiário faz prestação (status: PRESTACAO)
3. Se houver problema: criar `ContingenciaDiaria` em vez de deletar
4. Histórico preservado; auditoria rastreável

## 4. Security: RBAC com `@permission_required`

O Django admin (`/admin/`) é **proibido** para usuários operacionais. 

### Proteção global

Todo endpoint deve ser protegido:

```python
from django.contrib.auth.decorators import permission_required
from django.views.decorators.http import require_POST

@require_POST  # Rejeita GET antes de checkar permissão
@permission_required('pagamentos.operador_contas_a_pagar', raise_exception=True)
def avancar_processo_action(request, id):
    # Código aqui só roda se usuário tem permissão
    pass
```

**Não use:**
- ❌ `@login_required` (muito permissivo)
- ❌ `@user_passes_test` (difícil de auditar)
- ❌ `if not user.has_perm(...)` no corpo da função (fácil esquecer)

### Permissões no modelo

Defina em `models.py`:

```python
class Meta:
    permissions = [
        ("operador_contas_a_pagar", "Pode operar contas a pagar"),
        ("pode_analisar_prestacao_contas", "Pode analisar prestação de contas"),
        ("pode_autorizar_pagamento", "Pode autorizar pagamento"),
    ]
```

### Contexto: Acesso Contextual

Mesmo com permissão global, um usuário pode não ter acesso a um **registro específico**. Exemplo:

- Usuário A é "operador backoffice" e pode ver todos os processos
- Usuário B é "beneficiário de diária" e só pode ver sua própia diária

Validators contextuais vivem em `helpers.py` de cada módulo:

```python
# verbas_indenizatorias/views/diarias/helpers.py
def pode_acessar_prestacao(usuario, diaria):
    """Valida acesso contextual a uma diária"""
    
    # Case 1: Próprio beneficiário
    if diaria.beneficiario.usuario_id == usuario.id:
        return True
    
    # Case 2: Backoffice com permissão
    if usuario.has_perm('verbas_indenizatorias.analisar_prestacao_contas'):
        return True
    
    return False
```

Panel/Action chama:

```python
def detalhe_prestacao_panel(request, diaria_id):
    diaria = get_object_or_404(Diaria, id=diaria_id)
    
    if not pode_acessar_prestacao(request.user, diaria):
        raise PermissionDenied("Acesso negado a esta diária")
    
    return render(request, 'template.html', {'diaria': diaria})
```

## 5. Data Types: `decimal.Decimal` para dinheiro

**Jamais use `float` para dinheiro.**

- ❌ `valor = 1000.50` (float, impreciso)
- ✅ `valor = Decimal("1000.50")` (preciso)

Razão: Float tem erros de arredondamento:
```python
>>> 0.1 + 0.2
0.30000000000000004  # ❌ Errado!

>>> Decimal('0.1') + Decimal('0.2')
Decimal('0.3')  # ✅ Correto
```

Modelos:
```python
class Processo(models.Model):
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    # max_digits=12 = até R$ 9.999.999.999,99
    # decimal_places=2 = sempre dois dígitos centavos
```

Servicers e templates:
```python
# Sem conversão automática
processo.valor = Decimal("1000.00")
processo.save()

# Template: Django formata automaticamente
{{ processo.valor|floatformat:2 }}  # Saída: 1.000,00
```

## Checklist: Conformidade

Antes de submeter qualquer mudança que toque fluxo financeiro:

- ✅ Máquina de estado: todas transições no Service, não em Panel/Action
- ✅ Turnpikes: validações explícitas antes de transição
- ✅ Imutabilidade: nenhum `.delete()`; use flags `revogado`, `cancelado`
- ✅ Auditoria: fields timestamp + `django-simple-history` presentes
- ✅ RBAC: decorator `@permission_required` + contexto se necessário
- ✅ Decimal: todos valores monetários usam `Decimal('...')`
- ✅ Transactions: `transaction.atomic()` em operações multi-step
