# Monitoramento

## Localização dos Logs

### Logs da Aplicação Django (Gunicorn)

```bash
# Logs em tempo real do container web
docker compose logs -f web

# Últimas 200 linhas
docker compose logs --tail=200 web
```

O Django escreve para stdout/stderr, capturado pelo Docker. Em produção, redirecione para um agregador de logs (ex: Loki, CloudWatch, Sentry).

### Logs do Nginx

```bash
# Logs de acesso e erro do Nginx
docker compose logs -f nginx
```

Logs de acesso seguem o formato padrão Combined Log Format. Erros de proxy (502, 504) indicam problema no container `web`.

### Logs do PostgreSQL

```bash
docker compose logs -f db
```

---

## Health Check

O serviço `db` possui healthcheck nativo configurado no `docker-compose.yml` (`pg_isready`). O serviço `web` só inicia após o banco estar saudável.

!!! note "Endpoint de health check"
    A aplicação não expõe um endpoint `/health/` por padrão. Recomenda-se adicionar um endpoint simples que retorne `200 OK` para uso por load balancers e sistemas de monitoramento externos.

Para verificar o estado dos containers:

```bash
docker compose ps
```

---

## Indicadores a Monitorar

### Autenticação e Autorização

| Indicador | O que observar | Ação |
|---|---|---|
| Tentativas de login falhas | Múltiplos `401` em `/accounts/login/` | Investigar IP de origem; considerar rate limiting no Nginx |
| Bloqueios por RBAC | Pico de respostas `403` | Verificar se grupos/permissões foram configurados corretamente via `setup_grupos` |

### Uploads de Arquivo

| Indicador | O que observar | Ação |
|---|---|---|
| Rejeições de MIME | Mensagens `"Tipo de arquivo não permitido"` nos logs | Verificar se usuário está tentando subir arquivo inválido |
| Erros 413 do Nginx | `client intended to send too large body` | Arquivo excede 20 MB; revisar `client_max_body_size` se necessário |

### Integrações Externas

| Indicador | O que observar | Ação |
|---|---|---|
| Falhas Autentique | Exceções de API nos logs do `web` | Verificar `AUTENTIQUE_API_TOKEN` no `.env`; checar status da API |
| Divergências SISCAC | Mensagens de `divergência` no log de sync | Usar seleção manual de comprovante na interface |
| Falhas EFD-Reinf | Erros na transmissão de lotes | Verificar conectividade com o servidor da Receita Federal; revisar XMLs gerados |

### Banco de Dados

| Indicador | O que observar | Ação |
|---|---|---|
| Lentidão em queries | Tempo de resposta alto nas páginas de listagem | Verificar índices; usar `django-debug-toolbar` em dev |
| Erros de conexão | `OperationalError: could not connect to server` | Verificar healthcheck do serviço `db`; checar variáveis de ambiente |

---

## Alertas Recomendados

Configurar alertas para:

- Taxa de erro HTTP ≥ 5xx superior a 1% por minuto.
- Container `web` ou `db` em estado `unhealthy` ou `exited`.
- Espaço em disco do volume `postgres_data` acima de 80%.
- Latência média de resposta acima de 2 segundos.
