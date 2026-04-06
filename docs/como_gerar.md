# Como Gerar a Wiki

## Pré-requisitos

Instale as dependências de documentação no ambiente Python do projeto:

```bash
pip install mkdocs mkdocs-material mkdocstrings[python] pymdown-extensions
```

## Rodar localmente

```bash
mkdocs serve
```

Acesse o endereço exibido no terminal (normalmente `http://127.0.0.1:8000`).

## Gerar build estático

```bash
mkdocs build
```

Os arquivos finais serão gerados na pasta `site/`.

## Estrutura esperada

- `mkdocs.yml`: configuração principal da wiki.
- `docs/`: páginas Markdown da documentação.
- páginas com `::: modulo.python`: referências automáticas com mkdocstrings.