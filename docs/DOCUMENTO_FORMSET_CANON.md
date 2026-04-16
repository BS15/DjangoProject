# Documento Formset Genérico (Canon) — Guia de Integração

## Visão Geral

O widget `_documento_formset_generic.html` é o **componente canônico, reutilizável** para gerenciar documentos em qualquer módulo (fluxo, verbas, suprimentos, etc.).

Ele substitui:
- `fluxo/templates/fluxo/partials/_processo_doc_formset.html`
- `verbas_indenizatorias/templates/verbas/partials/_verba_doc_upload.html`
- Formulários inline em suprimentos

## Anatomia

### Template

```django
{% with formset=doc_formset form_prefix="documentos" tipos_documento=tipos_documento add_btn_class="btn-outline-primary" entity_label="Processo" pode_interagir=True show_order_field=True show_immutable_badge=True %}
  {% include "commons/partials/_documento_formset_generic.html" %}
{% endwith %}
```

### Parâmetros

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `formset` | Django FormSet | Seu FormSet de documentos (obrigatório) |
| `form_prefix` | str | Prefixo do FormSet, ex: `documentos`, `docorc` (obrigatório) |
| `tipos_documento` | QuerySet | `TiposDeDocumento.objects.all()` (obrigatório) |
| `add_btn_class` | str | Classe Bootstrap, ex: `btn-outline-primary` (default) |
| `entity_label` | str | Label da entidade, ex: "Processo", "Suprimento" (opcional) |
| `pode_interagir` | bool | Pode adicionar/remover documentos? (default: `True`) |
| `show_order_field` | bool | Mostrar campo de ordem e drag-handles? (default: `True`) |
| `show_immutable_badge` | bool | Mostrar badge "imutável"? (default: `True`) |

## Como Usar em Views

### Fluxo (Processo) — Exemplo Completo

**Em `fluxo/views/edicoes.py` (ou onde os processos são editados):**

```python
from django.forms import inlineformset_factory
from fluxo.models import Processo, Documento
from commons.shared.models import TiposDeDocumento

# Criar formset
DocumentoFormset = inlineformset_factory(
    Processo, Documento,
    fields=['ordem', 'tipo', 'arquivo'],
    extra=0,
    can_delete=True
)

def editar_processo(request, pk):
    processo = Processo.objects.get(pk=pk)
    doc_formset = DocumentoFormset(instance=processo)
    
    context = {
        'processo': processo,
        'doc_formset': doc_formset,
        'form_prefix': 'documentos',  # IMPORTANTE
        'tipos_documento': TiposDeDocumento.objects.all(),
        'add_btn_class': 'btn-outline-primary',
        'entity_label': f'Processo {processo.numero}',
    }
    return render(request, 'fluxo/editar_processo.html', context)
```

**Em `fluxo/templates/fluxo/editar_processo.html`:**

```django
{% extends "layouts/base_form.html" %}

{% block content %}
<form method="post">
    {% csrf_token %}
    
    <!-- Seu formulário de processo aqui -->
    {{ form.as_p }}
    
    <!-- DOCUMENTO FORMSET (CANON) -->
    {% with formset=doc_formset form_prefix="documentos" tipos_documento=tipos_documento add_btn_class="btn-outline-primary" entity_label=entity_label pode_interagir=True show_order_field=True show_immutable_badge=True %}
      {% include "commons/partials/_documento_formset_generic.html" %}
    {% endwith %}
    
    <button type="submit" class="btn btn-primary">Salvar</button>
</form>

<!-- IMPORTANTE: Incluir o script do gerenciador -->
<script src="{% static 'js/documento_formset_manager.js' %}"></script>
<script>
  new DocumentoFormsetManager('documentos');
</script>
{% endblock %}
```

### Verbas Indenizatórias (Diária, Reembolso) — Exemplo

**Em `verbas_indenizatorias/views/diarias.py`:**

```python
def editar_diaria(request, pk):
    diaria = Diaria.objects.get(pk=pk)
    
    # Formset inline para documentos da diária
    DiarioDocumentoFormset = inlineformset_factory(
        Diaria, DiarioDocumento,
        fields=['tipo', 'arquivo'],
        extra=1,
        can_delete=True
    )
    
    if request.method == 'POST':
        formset = DiarioDocumentoFormset(request.POST, request.FILES, instance=diaria)
        if formset.is_valid():
            formset.save()
            return redirect('diaria_detail', pk=pk)
    else:
        formset = DiarioDocumentoFormset(instance=diaria)
    
    context = {
        'diaria': diaria,
        'doc_formset': formset,
        'form_prefix': 'documentos',
        'tipos_documento': TiposDeDocumento.objects.all(),
        'add_btn_class': 'btn-outline-success',
        'entity_label': f'Diária {diaria.numero}',
    }
    return render(request, 'verbas/editar_diaria.html', context)
```

**Em `verbas_indenizatorias/templates/verbas/editar_diaria.html`:**

```django
{% with formset=doc_formset form_prefix="documentos" tipos_documento=tipos_documento add_btn_class="btn-outline-success" entity_label=entity_label pode_interagir=True show_order_field=False %}
  {% include "commons/partials/_documento_formset_generic.html" %}
{% endwith %}

<script src="{% static 'js/documento_formset_manager.js' %}"></script>
<script>
  new DocumentoFormsetManager('documentos');
</script>
```

### Suprimentos — Exemplo

**Em `suprimentos/views/despesas.py`:**

```python
def editar_despesa_suprimento(request, pk):
    despesa = DespesaSuprimento.objects.get(pk=pk)
    
    # Formset inline para documentos do suprimento
    DespesaDocumentoFormset = inlineformset_factory(
        DespesaSuprimento, DespesaDocumento,
        fields=['tipo', 'arquivo'],
        extra=1,
        can_delete=True
    )
    
    if request.method == 'POST':
        formset = DespesaDocumentoFormset(request.POST, request.FILES, instance=despesa)
        if formset.is_valid():
            formset.save()
            return redirect('despesa_detail', pk=pk)
    else:
        formset = DespesaDocumentoFormset(instance=despesa)
    
    context = {
        'despesa': despesa,
        'doc_formset': formset,
        'form_prefix': 'documentos',
        'tipos_documento': TiposDeDocumento.objects.all(),
        'add_btn_class': 'btn-outline-warning',
        'entity_label': f'Suprimento {despesa.numero}',
        'pode_interagir': not despesa.finalizado,  # Conditional
    }
    return render(request, 'suprimentos/editar_despesa.html', context)
```

**Em `suprimentos/templates/suprimentos/editar_despesa.html`:**

```django
{% with formset=doc_formset form_prefix="documentos" tipos_documento=tipos_documento add_btn_class="btn-outline-warning" entity_label=entity_label pode_interagir=pode_interagir %}
  {% include "commons/partials/_documento_formset_generic.html" %}
{% endwith %}

<script src="{% static 'js/documento_formset_manager.js' %}"></script>
<script>
  new DocumentoFormsetManager('documentos');
</script>
```

## Tratamento de Formulários (Backend)

Quando o formulário com o formset for submetido, Django tratará automaticamente as adições/remoções/atualizações:

```python
if request.method == 'POST':
    formset = YourDocumentFormset(request.POST, request.FILES, instance=entity)
    
    if formset.is_valid():
        formset.save()  # Django cuida de CREATE/UPDATE/DELETE automaticamente
        messages.success(request, "Documentos salvos com sucesso!")
        return redirect(...)
    else:
        messages.error(request, "Erro ao salvar documentos.")
```

## Modelos Esperados

O widget assume que você ter estes modelos:

```python
class MinhaEntidade(models.Model):
    numero = models.CharField(max_length=50)
    # ... outros campos

class MeuDocumento(models.Model):
    entidade = models.ForeignKey(MinhaEntidade, on_delete=models.CASCADE)
    tipo = models.ForeignKey(TiposDeDocumento, on_delete=models.PROTECT)
    arquivo = models.FileField(upload_to=caminho_documento)
    ordem = models.IntegerField(default=0)
    imutavel = models.BooleanField(default=False)  # Opcional
    
    class Meta:
        ordering = ['ordem']
```

## Customizações Avançadas

### Variar a cor do botão por módulo

```django
{# fluxo (azul) #}
{% with add_btn_class="btn-outline-primary" %}...{% endwith %}

{# verbas (verde) #}
{% with add_btn_class="btn-outline-success" %}...{% endwith %}

{# suprimentos (amarelo) #}
{% with add_btn_class="btn-outline-warning" %}...{% endwith %}

{# fiscal (vermelho) #}
{% with add_btn_class="btn-outline-danger" %}...{% endwith %}
```

### Desabilitar reordenação

```django
{% with show_order_field=False %}
  {% include "commons/partials/_documento_formset_generic.html" %}
{% endwith %}
```

### Formulários read-only

```django
{% with pode_interagir=False %}
  {% include "commons/partials/_documento_formset_generic.html" %}
{% endwith %}
```

## Migração de Código Existente

### De `fluxo/_processo_doc_formset.html` para o canon

**Antes:**
```django
{% include "fluxo/partials/_processo_doc_formset.html" with formset=doc_formset %}
```

**Depois:**
```django
{% with formset=doc_formset form_prefix="documentos" tipos_documento=tipos_documento add_btn_class="btn-outline-primary" %}
  {% include "commons/partials/_documento_formset_generic.html" %}
{% endwith %}
```

### De `verbas/_verba_doc_upload.html` para o canon

**Antes:**
```django
{% include "verbas/partials/_verba_doc_upload.html" with verba=diaria btn_class="btn-outline-success" %}
```

**Depois:**
```django
{% with formset=doc_formset form_prefix="documentos" tipos_documento=tipos_documento add_btn_class="btn-outline-success" %}
  {% include "commons/partials/_documento_formset_generic.html" %}
{% endwith %}
```

(Verbas deixará de usar AJAX e usará FormSet como fluxo — mais consistente)

## Dependências

- Django >= 3.2
- jQuery (para o gerenciador JavaScript)
- Bootstrap 5 (para estilos CSS e ícones bi)

## Checklist de Integração

- [ ] View passa `doc_formset`, `form_prefix`, `tipos_documento` para o contexto
- [ ] Template inclui `commons/partials/_documento_formset_generic.html`
- [ ] Script `documento_formset_manager.js` incluído no fino da página
- [ ] `new DocumentoFormsetManager('seu_prefix')` chamado no `<script>` da página
- [ ] Backend trata `formset.save()` corretamente no POST
- [ ] Testes passam: `python manage.py test seu_app`

## Troubleshooting

**P: Botão "Adicionar Documento" não funciona**
- R: Confirme que `documento_formset_manager.js` está incluído
- R: Confirme que `DocumentoFormsetManager('seu_prefix')` foi instanciado com o prefixo correto

**P: Documentos não salvam após submissão**
- R: Confirm que o backend chama `formset.save()`
- R: Verifique erros em `formset.errors`

**P: Campos aparecendo com IDs estranhos**
- R: Verifique que `form_prefix` no template bate com o prefixo do FormSet Django

---

**Última revisão**: Standardization Canon v1
