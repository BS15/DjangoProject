# Deploy

## Topologia Docker Compose

O ambiente de produção é composto por três serviços:

```
┌─────────┐     HTTP      ┌──────────────┐     WSGI      ┌──────────────┐
│  Nginx  │ ────────────► │   Gunicorn   │ ────────────► │    Django    │
│ :80     │               │   web:8000   │               │   + uWSGI    │
└─────────┘               └──────────────┘               └──────────────┘
                                  │
                           ┌──────▼──────┐
                           │ PostgreSQL  │
                           │ db:5432     │
                           └─────────────┘
```

- **nginx:** proxy reverso, serve arquivos estáticos e de media diretamente.
- **web:** aplicação Django rodando em Gunicorn.
- **db:** PostgreSQL 15.

Volumes persistentes:
- `postgres_data` — dados do banco.
- `static_volume` — arquivos estáticos coletados.
- `media_volume` — uploads de usuários.

---

## Variáveis de Ambiente

Copie `.env.example` para `.env` e preencha **todas** as variáveis antes de subir o ambiente:

```bash
cp .env.example .env
```

| Variável | Obrigatória | Descrição |
|---|---|---|
| `SECRET_KEY` | ✅ | Chave secreta Django. Gere com `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DEBUG` | ✅ | `False` em produção, `True` em desenvolvimento |
| `ALLOWED_HOSTS` | ✅ | Lista separada por vírgula dos hosts permitidos |
| `CSRF_TRUSTED_ORIGINS` | ✅ | Origens confiáveis para CSRF (incluir scheme: `https://dominio.com`) |
| `DB_ENGINE` | ✅ | Ex: `django.db.backends.postgresql` |
| `DB_NAME` | ✅ | Nome do banco de dados |
| `DB_USER` | ✅ | Usuário do banco |
| `DB_PASSWORD` | ✅ | Senha do banco |
| `DB_HOST` | ✅ | Host do banco (`db` no Docker Compose) |
| `DB_PORT` | ✅ | Porta do banco (`5432`) |
| `POSTGRES_DB` | ✅ | Nome do banco usado pelo serviço `db` do Compose |
| `POSTGRES_USER` | ✅ | Usuário do serviço `db` |
| `POSTGRES_PASSWORD` | ✅ | Senha do serviço `db` |
| `STATIC_ROOT` | ✅ | Caminho absoluto para `collectstatic` (ex: `/app/staticfiles`) |
| `AUTENTIQUE_API_TOKEN` | Condicional | Obrigatório para envio de documentos à Autentique |
| `SECURE_SSL_REDIRECT` | Recomendado | `True` em produção atrás de proxy com SSL |
| `USE_X_FORWARDED_PROTO` | Recomendado | `True` quando atrás de proxy confiável |
| `GUNICORN_WORKERS` | Opcional | Número de workers Gunicorn (padrão: 3) |

---

## Procedimento de Deploy

### Primeiro Deploy

```bash
# 1. Clonar o repositório e configurar o ambiente
cp .env.example .env
# Editar .env

# 2. Subir todos os serviços
docker compose up --build -d

# 3. Criar superusuário inicial
docker compose exec web python manage.py createsuperuser
```

O `docker compose up` executa automaticamente, na ordem:

1. `python manage.py migrate --noinput`
2. `python manage.py collectstatic --noinput`
3. `python manage.py setup_grupos`
4. `python manage.py setup_baselines`
5. Gunicorn inicia.

### Atualização (Deploy Contínuo)

```bash
# 1. Obter nova versão do código
git pull origin main

# 2. Recriar a imagem e reiniciar o serviço web
docker compose up --build -d web

# 3. Verificar logs
docker compose logs -f web
```

!!! note "Sem downtime zero garantido"
    O comando acima causa breve interrupção durante o restart do container `web`. Para deploys sem downtime, configure um load balancer externo com múltiplas instâncias.

---

## Configuração Nginx

O arquivo de configuração fica em `nginx/nginx.conf` e é montado como volume read-only no container Nginx.

Pontos relevantes:

- `client_max_body_size 20M` — limite de upload alinhado com a validação da aplicação.
- `/static/` → alias para `static_volume` com cache de 30 dias.
- `/media/` → alias para `media_volume` com `X-Content-Type-Options: nosniff`.
- Todo o restante é proxiado para `web:8000` com headers `X-Forwarded-For` e `X-Forwarded-Proto`.

Para SSL, adicione um server block com `listen 443 ssl` e configure os certificados antes do bloco existente.

---

## Arquivos Estáticos e Migrações

Os arquivos estáticos e migrações são executados automaticamente no startup do container `web`. Para executar manualmente:

```bash
# Apenas migrações
docker compose exec web python manage.py migrate

# Apenas collectstatic
docker compose exec web python manage.py collectstatic --noinput
```
