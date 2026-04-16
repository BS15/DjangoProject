# Setup do Ambiente

## Pré-requisitos
- Docker e Docker Compose.
- Arquivo `.env` com variáveis obrigatórias do projeto.

## Subida do ambiente
```bash
docker compose up --build
```

## Banco de dados em modo de desenvolvimento
Projeto em modo pré-V1 com protocolo de base limpa quando necessário.

Fluxo comum:
```bash
python manage.py migrate
python manage.py createsuperuser
```

## Seed e dados de apoio
Quando houver scripts de carga, execute-os após preparar o banco para viabilizar cenários de teste funcional.
