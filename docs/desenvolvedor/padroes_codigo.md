# Padrões de Código

## Arquitetura de views
- `panels.py`: apenas leitura (`GET`) e renderização.
- `actions.py`: apenas escrita (`POST`) e redirecionamento.
- Regras de negócio e mutações: `services/`.

## Templates em camadas
Sempre estender os layouts base:
- `layouts/base_list.html`
- `layouts/base_form.html`
- `layouts/base_review.html`
- `layouts/base_detail.html`

## DRY e reutilização
- Priorizar mixins, filtros e helpers reutilizáveis.
- Evitar duplicação de validações entre módulos.
- Replicar padrões existentes de módulos análogos antes de criar abordagens novas.

## Estado e compliance
- Tratar progressão de etapas como máquina de estados.
- Aplicar turnpikes antes de qualquer avanço de fase.
- Preservar auditabilidade como requisito de primeira classe.
