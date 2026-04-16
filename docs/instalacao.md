# Guia de Instalação

## Opção recomendada (Docker)
1. Configure o arquivo `.env` com as variáveis necessárias.
2. Suba os serviços:
   ```bash
   docker compose up --build
   ```

## Opção local (sem Docker)
1. Instale dependências:
   ```bash
   pip install -r requirements.txt
   ```
2. Prepare o banco:
   ```bash
   python manage.py migrate
   ```
3. Inicie o servidor:
   ```bash
   python manage.py runserver
   ```

## Documentação local
```bash
mkdocs serve
```
