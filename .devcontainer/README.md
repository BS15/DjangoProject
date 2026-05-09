# Dev Container Configuration

Este diretório contém a configuração do ambiente de desenvolvimento em container para o projeto Django.

## 📋 O Que Está Incluído

- **Python 3.11** - Mesma versão usada em produção
- **Sistema de Build** - gcc, libpq-dev para compilação de pacotes nativos
- **PostgreSQL Client** - Para conexão com banco de dados
- **Sandbox Tools** - bubblewrap e socat para execução segura de agentes de IA
- **VS Code Extensions** - Python, Django, Ruff, Black, GitLens, etc.
- **Dev Dependencies** - pytest, pytest-django, black, ruff, ipython, django-extensions

## 🚀 Como Usar

### No VS Code / Codespaces

1. **Abrir em container:**
   - Pressione `Ctrl+Shift+P` (ou `Cmd+Shift+P` no Mac)
   - Digite "Dev Containers: Rebuild and Reopen in Container"
   - O container será criado automaticamente

2. **Após a primeira criação:**
   - Todas as dependências serão instaladas automaticamente
   - O ambiente estará pronto para desenvolvimento

### Portas Disponíveis

- **8000** - Django Development Server
- **5432** - PostgreSQL (se usar banco local)

## 🔧 Arquivos

- `devcontainer.json` - Configuração principal do container
- `post-create.sh` - Script executado após criação do container para instalar dependências

## 💡 Dicas

- O container monta seu diretório `.ssh` para usar as mesmas chaves Git
- Variáveis de ambiente Django são configuradas automaticamente
- Python linting com Ruff e formatação com Black estão habilitados

## ❌ Troubleshooting

**Erro: "missing sandbox dependencies"**
- Isso foi resolvido automaticamente com bubblewrap e socat instalados
- Se ainda assim ocorrer, reconstrua o container

**Container lento ou com problemas**
- Execute: `Dev Containers: Rebuild Container` para limpar e reconstruir
