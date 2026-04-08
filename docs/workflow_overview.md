# Fluxo Orçamentário - Visão Geral

Este sistema segue uma máquina de estados rígida para execução orçamentária pública.

## Estados Oficiais

1. A EMPENHAR
2. AGUARDANDO LIQUIDAÇÃO
3. A PAGAR
4. PAGO
5. CONTABILIZADO
6. ARQUIVADO

## Princípios do Fluxo

- As transições devem respeitar regras de negócio e validações obrigatórias.
- Registros em estágios avançados não devem ser removidos, preservando trilha de auditoria.
- Evidências documentais (fiscal, comprovações e assinatura) sustentam a progressão de estado.

## Módulos centrais do fluxo

::: processos.views.fluxo.helpers

::: processos.services.shared.documentos

::: processos.views.fluxo.security
