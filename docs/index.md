# Wiki PaGé

Bem-vindo ao portal de documentação do PaGé.

Esta wiki foi organizada para atender dois públicos ao mesmo tempo:
- Negócio e operação: entendimento da esteira de pagamentos e compliance.
- Engenharia: padrões arquiteturais, responsabilidades por módulo e práticas de desenvolvimento.

Use o menu lateral para navegar por:
- Visão Geral e Negócio
- Arquitetura de Software
- Manual de Módulos (Funcional)
- Fluxos Operacionais Detalhados
- Segurança e Governança
- Guia do Desenvolvedor

## Fluxos Operacionais Detalhados

Análise step-by-step de cada domínio de negócio, incluindo máquinas de estado, [turnpikes](/negocio/glossario_conselho.md#turnpike), permissões e referências de código:

- [Pagamentos](fluxos/pagamentos.md) — esteira completa de A EMPENHAR até ARQUIVADO.
- [Retenções](fluxos/retencoes.md) — ciclo de `RetencaoImposto` da [Nota Fiscal](/negocio/glossario_conselho.md#nota-fiscal) ao recolhimento.
- [Diárias](fluxos/diarias.md) — cadastro, prestação de contas, [contingência](/negocio/glossario_conselho.md#contingencia) e [devolução](/negocio/glossario_conselho.md#devolucao).
- [Suprimento de Fundos](fluxos/suprimento_fundos.md) — conceção, despesas e fechamento da prestação.
- [Cancelamento](fluxos/cancelamento.md) — [cancelamento](/negocio/glossario_conselho.md#cancelamento) formal de processos, verbas e suprimentos, com [devolução](/negocio/glossario_conselho.md#devolucao) obrigatória quando pago.
