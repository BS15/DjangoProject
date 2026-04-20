# Setup do Ambiente

## Pré-requisitos
- Docker e Docker Compose.
- Arquivo `.env` com variáveis obrigatórias do projeto.

## Variáveis de Ambiente
Copie `.env.example` para `.env` e preencha as variáveis obrigatórias:

```bash
cp .env.example .env
```

Consulte os comentários em `.env.example` para descrição de cada variável. As variáveis essenciais incluem configuração do banco de dados PostgreSQL, chave secreta Django (`SECRET_KEY`), modo de debug e, quando aplicável, token da API Autentique.

## Subida do ambiente
```bash
docker compose up --build
```

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
pytest
```

A configuração está em `pytest.ini` na raiz do projeto. Para executar um módulo específico:

```bash
pytest fiscal/
pytest pagamentos/
```

## Seed e dados de apoio
Para viabilizar cenários de teste funcional, execute os scripts de carga após preparar o banco. Verifique se existem scripts de seed disponíveis na raiz do projeto ou em `desenvolvedor/` e execute-os conforme documentado nos próprios scripts.
