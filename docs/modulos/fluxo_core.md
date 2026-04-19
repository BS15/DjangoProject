# Fluxo Core

O módulo `fluxo` é o núcleo da gestão dos processos de pagamento no PaGé.

## Papel no sistema
- Orquestrar o ciclo de vida do processo administrativo-financeiro.
- Controlar etapas, documentos obrigatórios e prontidão para avanço.
- Expor o Hub principal de acompanhamento do processo.

## Máquina de estados
A progressão ocorre por estágios com regras de entrada e saída (turnpikes). A trilha principal do processo segue a sequência abaixo; etapas e nomes exatos estão definidos como constantes em `fluxo/domain_models/processo.py`.

Trilha principal (status canônicos):
- A EMPENHAR
- AGUARDANDO LIQUIDAÇÃO
- EM LIQUIDAÇÃO
- A PAGAR
- AGUARDANDO AUTORIZAÇÃO
- EM LANÇAMENTO
- PAGO
- EM CONFERENCIA
- EM CONTABILIZACAO
- CONTABILIZADO
- EM CONSELHO
- A ARQUIVAR
- ARQUIVADO

Caminhos laterais (fluxos de exceção):
- **Contingência**: desvia o processo para análise multi-nível (supervisor -> ordenador -> conselho) sem bloquear o status principal. Após aprovação, o efeito é aplicado ao processo e ele retoma a trilha.
- **Devolução**: registra reversão formal de valor ou documento, podendo ajustar o status do processo e gerar pendências.
- **Recusa** (em etapas de aprovação): devolve o processo ao status anterior com registro formal de motivo e criação de pendência.

Para o comportamento exato de cada transição e seus turnpikes, consulte `fluxo/domain_models/processo.py` e os serviços em `fluxo/services/`.

## Turnpikes
Cada transição é bloqueada até que os requisitos da etapa estejam completos (documentos, validações fiscais, autorizações e consistência cadastral).
