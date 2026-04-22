# Backup e Restore

## Backup do PostgreSQL

### Via Docker Compose

```bash
# Dump completo do banco (formato custom, comprimido)
docker compose exec db pg_dump \
  -U ${POSTGRES_USER} \
  -d ${POSTGRES_DB} \
  -Fc \
  -f /tmp/backup_$(date +%Y%m%d_%H%M%S).dump

# Copiar o dump para o host
docker compose cp db:/tmp/backup_*.dump ./backups/
```

### Via volume Docker (alternativa)

```bash
# Identifica o nome do volume
docker volume ls | grep postgres_data

# Backup usando container auxiliar
docker run --rm \
  -v djangoproject_postgres_data:/data \
  -v $(pwd)/backups:/backup \
  alpine \
  tar czf /backup/postgres_data_$(date +%Y%m%d).tar.gz -C /data .
```

---

## Restore do PostgreSQL

!!! warning "Atenção"
    O restore destrói todos os dados existentes no banco. Certifique-se de ter um backup válido antes de prosseguir.

```bash
# 1. Parar a aplicação (manter apenas o banco)
docker compose stop web nginx

# 2. Restaurar o dump
docker compose exec -T db pg_restore \
  -U ${POSTGRES_USER} \
  -d ${POSTGRES_DB} \
  --clean \
  --if-exists \
  /tmp/backup_YYYYMMDD_HHMMSS.dump

# 3. Reiniciar a aplicação
docker compose start web nginx
```

Para restaurar o dump, primeiro copie o arquivo para dentro do container:

```bash
docker compose cp ./backups/backup_YYYYMMDD.dump db:/tmp/
```

---

## Restore para Ponto Específico no Tempo

O projeto não configura WAL archiving ou streaming replication por padrão. A recuperação point-in-time (PITR) não está disponível na configuração padrão.

Para ambientes de produção críticos, recomenda-se configurar `wal_level = replica` e arquivamento contínuo com uma solução como pgBackRest ou barman.

---

## Clean Slate Protocol (Desenvolvimento)

Durante a fase pré-V1, mudanças de schema incompatíveis são resolvidas com reinicialização completa do banco. Consulte também [Setup do Ambiente](../desenvolvedor/setup_ambiente.md).

### Opção 1 — Reinicialização via Django (sem Docker)

```bash
python manage.py flush --no-input
python manage.py migrate
python manage.py createsuperuser
```

### Opção 2 — Reinicialização completa via Docker (recomendada para schema quebrado)

```bash
# Destrói containers E volumes (apaga todos os dados)
docker compose down -v

# Recria tudo do zero
docker compose up --build

# Cria superusuário
docker compose exec web python manage.py createsuperuser
```

!!! warning "Perda de dados"
    `docker compose down -v` remove todos os volumes nomeados, incluindo `postgres_data`, `static_volume` e `media_volume`. Use apenas em ambiente de desenvolvimento.
