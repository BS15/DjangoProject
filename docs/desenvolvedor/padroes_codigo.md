# Padrões de Código

## Arquitetura de views
- `panels.py`: apenas leitura (`GET`) e renderização.
- `actions.py`: apenas escrita (`POST`) e redirecionamento.
- Regras de negócio e mutações: `services/`. (Ver [Manager-Worker](../arquitetura/manager_worker.md))

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

## Documentação operacional de Actions
A especificação operacional (catálogo por action, uma entrada por endpoint) fica centralizada em [Dicionários Operacionais](dicionarios_operacionais.md).

Regra de separação entre os guias:
- esta página define princípios arquiteturais e padrões transversais.
- a página de dicionários lista contratos concretos de cada action e worker.

## Estado e compliance
- Tratar progressão de etapas como máquina de estados. (Ver [Domain Knowledge](../arquitetura/domain_knowledge.md))
- Aplicar [turnpikes](/negocio/glossario_conselho.md#turnpike) antes de qualquer avanço de fase.
- Preservar auditabilidade como requisito de primeira classe.
