# PaGé — Sistema de Backoffice Financeiro e Administrativo

> **Status:** Pré-V1 — desenvolvimento ativo, base de dados em Clean Slate Protocol.

PaGé é um ERP de backoffice financeiro e administrativo desenvolvido para entidades de administração pública brasileira (Conselhos). Centraliza a esteira completa de pagamentos, verbas indenizatórias, suprimentos de fundos, retenção de impostos e gestão de credores, com rastreabilidade e conformidade como requisitos de primeira classe.

---

## Domínios

| Domínio | Responsabilidade |
|---|---|
| **Pagamentos** | Esteira principal: A EMPENHAR → PAGO → ARQUIVADO. Gestão de processos, notas fiscais, devoluções, contingências e integração SISCAC. |
| **Verbas Indenizatórias** | Diárias, reembolsos, auxílios e jetons — da solicitação ao agrupamento em processo de pagamento. |
| **Suprimentos de Fundos** | Concessão de adiantamento, registro de despesas e encerramento formal da prestação de contas. |
| **Fiscal** | Retenções de impostos, geração e transmissão de lotes EFD-Reinf. |
| **Credores** | Cadastro e manutenção de fornecedores e dados bancários. |
| **Commons** | Infraestrutura transversal: autenticação, layouts, validação de arquivos, formulários e auditoria. |

---

## Início Rápido (Docker)

```bash
# 1. Clonar e configurar variáveis de ambiente
cp .env.example .env
# Editar .env com SECRET_KEY, credenciais do banco e demais variáveis obrigatórias

# 2. Subir o ambiente
docker compose up --build

# 3. A aplicação estará disponível em http://localhost
```

O `docker compose up` executa automaticamente `migrate`, `collectstatic`, `setup_grupos` e `setup_baselines` antes de iniciar o Gunicorn.

Para criar o superusuário inicial:

```bash
docker compose exec web python manage.py createsuperuser
```

Consulte o [Guia do Desenvolvedor](docs/desenvolvedor/setup_ambiente.md) para opções locais (sem Docker) e o protocolo de reinicialização de banco.

---

## Arquitetura

O PaGé adota dois padrões arquiteturais centrais:

- **Manager-Worker:** Views separadas por método HTTP — `panels.py` (GET, leitura) e `actions.py` (POST, mutação). Toda lógica de negócio vive em `services/`.
- **Hub-and-Spoke:** Páginas de detalhe são centros de comando somente leitura; mutações ocorrem em endpoints dedicados que redirecionam de volta ao hub.

Documentação completa na [wiki do projeto](docs/arquitetura/manager_worker.md).

---

## Stack

| Componente | Tecnologia |
|---|---|
| Framework web | Django |
| Banco de dados | PostgreSQL 15 |
| Trilha de auditoria | django-simple-history |
| Documentação | MkDocs Material |
| Servidor de aplicação | Gunicorn |
| Proxy reverso | Nginx |

---

## Documentação

```bash
mkdocs serve
```

Acesse em `http://127.0.0.1:8000` para navegar pela wiki completa (arquitetura, fluxos, RBAC, referência de API, operações).

A versão HTML estática publicada via GitHub Pages está disponível em https://BS15.github.io/DjangoProject/.
Ao atualizar arquivos em `docs/`, mantenha também o espelho correspondente em `site/` sincronizado.

---

## Links

- [Guia de Contribuição](CONTRIBUTING.md)
- [Política de Segurança](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [Documentação Estática (GitHub Pages)](https://BS15.github.io/DjangoProject/)
- [Wiki — Setup do Ambiente](docs/desenvolvedor/setup_ambiente.md)
- [Wiki — Padrões de Código](docs/desenvolvedor/padroes_codigo.md)
- [Wiki — Matriz de Permissões](docs/governanca/matriz_permissoes.md)
