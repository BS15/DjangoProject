# Setup do Ambiente

## Pré-requisitos
- Docker e Docker Compose.
- Arquivo `.env` com variáveis obrigatórias do projeto.

## Variáveis de Ambiente
Copie `.env.example` para `.env` e preencha as variáveis obrigatórias:

```bash
cp .env.example .env
```

As variáveis que **devem** ser preenchidas antes do primeiro `docker compose up`:

| Variável | Descrição |
|---|---|
| `SECRET_KEY` | Chave secreta Django — gere uma nova com `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `POSTGRES_PASSWORD` / `DB_PASSWORD` | Senha do banco — use o mesmo valor em ambas |
| `ALLOWED_HOSTS` | Hosts permitidos (padrão: `127.0.0.1,localhost`) |
| `CSRF_TRUSTED_ORIGINS` | Origens confiáveis para CSRF (padrão: `http://localhost,http://127.0.0.1`) |

As demais variáveis (`DB_ENGINE`, `DB_NAME`, `DB_HOST`, `DB_PORT`, `DB_USER`, `STATIC_ROOT`) já estão pré-configuradas para o stack Docker em `.env.example` e não precisam ser alteradas para um primeiro boot.

## Subida do ambiente
```bash
docker compose up --build
```

O `docker compose up` executa automaticamente `migrate`, `collectstatic` e `setup_headstart` (inicializa catálogos financeiros e grupos/permissões) antes de iniciar o Gunicorn.

## Banco de dados em modo de desenvolvimento
Projeto em modo pré-V1 com protocolo de base limpa (Clean Slate Protocol).

Para inicializar ou reinicializar completamente o banco:
```bash
python manage.py flush --no-input
python manage.py migrate
python manage.py createsuperuser
```

Para uma reinicialização total (útil quando há mudanças de schema incompatíveis):
```bash
# Destruir e recriar o banco no container Docker
docker compose down -v
docker compose up --build
python manage.py migrate
python manage.py createsuperuser
```

## Executando os Testes
O projeto usa pytest com o plugin Django.

```bash
python3 -m pytest -q
```

A configuração está em `pytest.ini` na raiz do projeto. Para executar um módulo específico:

```bash
python3 -m pytest -q apps/retencoes/tests
python3 -m pytest -q apps/pagamentos/tests
```

## Seed e dados de apoio
Para viabilizar cenários de teste funcional, execute os scripts de carga após preparar o banco. Verifique se existem scripts de seed disponíveis na raiz do projeto ou em `desenvolvedor/` e execute-os conforme documentado nos próprios scripts.

## Opção local (sem Docker)

1. Instale dependências:
   ```bash
   pip install -r requirements.txt
   ```
2. Ajuste o bloco de banco no `.env` para SQLite (veja o bloco comentado "Local-only" em `.env.example`).
3. Prepare o banco:
   ```bash
   python manage.py migrate
   ```
4. Inicie o servidor:
   ```bash
   python manage.py runserver
   ```

## Documentação local

```bash
mkdocs serve
```
