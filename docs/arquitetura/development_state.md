# Estado de Desenvolvimento: FULL DEV MODE (Pré-V1)

O PaGé está em fase ativa de desenvolvimento pré-produção. Durante este estado, todos os decisões arquiteturais priorizam **velocidade iterativa** e **clareza de intenção** sobre compatibilidade com versões anteriores.

## Canonical Changes Only

Na fase FULL DEV MODE, mudanças no código DEVEM ser implementadas diretamente no estado **canônico** da estrutura, sem camadas intermediárias de compatibilidade.

### O que isto significa:

**NÃO escrever:**
- Shims de compatibilidade
- Wrappers de deprecação  
- Fallback logic para código legado
- Data migrations complexas

**Escrever:**
- Alterações diretas em `models.py`
- Refatorações brutais de estrutura de arquivos
- Remoção agressiva de código não utilizado

### Exemplo

Se um modelo `Diaria` precisa ganhar um novo campo obrigatório ou mudar sua estrutura:

❌ **Errado:** criar um data migration que popula o campo em registros históricos
✅ **Correto:** alterar `models.py` e deixar o banco ser resetado

## Clean Slate Protocol

O banco de dados pode ser **destruído e recriado** a qualquer momento durante o desenvolvimento. Isto significa:

1. Não versione dados de produção localmente
2. Não se preocupe com dados sintéticos em `db.sqlite3`
3. Ao sincronizar com `main`, se encontrar conflito de migração: `rm db.sqlite3 && python manage.py migrate`

### Workflow esperado:

```
git pull origin main
rm db.sqlite3                    # Clean slate
python manage.py migrate
python manage.py gerar_dados_fake  # Recarregar dados de teste
```

Se uma refatoração quebrou modelos existentes, a solução é sempre **resetar o banco**, nunca escrever una migration complexa de transformação de dados.

## Implicações para Arquitetura

Este estado de desenvolvimento habilita:

- **Refatorações modulares agressivas:** quebrar grandes apps em domínios isolados sem se preocupar com shims
- **Limpeza de código histórico:** remover padrões antigos ou ineficientes sem transição gradual
- **Mudanças de naming estrutural:** renomear models, views, arquivos e pastas sem preocupação com links históricos

Quando V1 publica, o sistema passa para **Production Mode**, onde estas práticas viram proibidas e data migrations viram obrigatórias.
