# Pagamentos Core

O módulo `pagamentos` é o núcleo da gestão dos processos de pagamento no PaGé.

## Papel no sistema
- Orquestrar o ciclo de vida do processo administrativo-financeiro.
- Controlar etapas, documentos obrigatórios e prontidão para avanço.
- Expor o Hub principal de acompanhamento do processo.

## Máquina de estados
A progressão ocorre por estágios com regras de entrada e saída.

Exemplo de trilha macro:
- A EMPENHAR
- AGUARDANDO LIQUIDAÇÃO
- A PAGAR
- PAGO
- CONTABILIZADO
- ARQUIVADO

## Turnpikes
Cada transição é bloqueada até que os requisitos da etapa estejam completos (documentos, validações fiscais, autorizações e consistência cadastral).
