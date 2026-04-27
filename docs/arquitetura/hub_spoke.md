# Interface Hub-and-Spoke

## O problema das telas monolíticas

Sistemas de backoffice financeiro costumam crescer em direção a formulários gigantes: uma tela com dezenas de campos, múltiplas seções colapsáveis, e lógica de salvamento que tenta cobrir todos os casos de uma única vez. O resultado é complexidade de renderização, risco de inconsistência transacional e interfaces difíceis de operar.

O PaGé adota o padrão Hub-and-Spoke para evitar esse crescimento. A premissa é simples: separar *leitura e visibilidade* (o Hub) de *execução de tarefas* (os Spokes).

## O Hub — Painel de Comando

A tela de detalhe de cada entidade principal (um processo de pagamento, um suprimento de fundos, uma verba indenizatória) funciona como um painel de comando de leitura. Ela consolida em uma única visão o estado atual do registro: status corrente, documentos anexados, histórico de movimentações, validações pendentes e ações disponíveis para o próximo passo.

O Hub não contém formulários de edição inline. Ele apresenta o estado e oferece pontos de navegação para as tarefas disponíveis.

## Os Spokes — Tarefas Isoladas

Cada operação de mutação — anexar um documento, aprovar uma etapa, registrar uma nota fiscal, lançar um pagamento — acontece em seu próprio endpoint dedicado. Esse endpoint recebe apenas os dados necessários para aquela operação específica, valida, executa via Service, e redireciona de volta ao Hub. Para a separação por método e responsabilidades, veja [Padrão Manager-Worker](manager_worker.md).

Essa isolação traz três consequências práticas:

**Menor superfície de erro por tela**: cada Spoke lida com um conjunto pequeno e coeso de dados, reduzindo o risco de um campo irrelevante causar falha em uma operação distante.

**Transações mais limpas**: como cada Spoke executa uma única operação, o `transaction.atomic()` do Service envolve apenas os registros relevantes — sem o risco de um save() amplo comprometer registros não intencionais.

**Rastreabilidade**: o histórico de auditoria (`django-simple-history`) registra operações pontuais e discretas, não salvamentos em massa que modificam múltiplos campos ao mesmo tempo.

Detalhes de requisitos e cobertura de evidências: [Trilha de Auditoria](../governanca/trilha_auditoria.md).

## Relação com o padrão Manager-Worker

O Hub é renderizado por um Panel (GET). Cada Spoke é executado por uma Action (POST) que delega para um Service. A arquitetura Hub-and-Spoke é, portanto, a expressão na interface do usuário do [Padrão Manager-Worker](manager_worker.md) na camada de código.

Exemplos concretos de aplicação do padrão:

- [Fluxo: Diárias](../fluxos/diarias.md)
- [Fluxo: Pagamentos](../fluxos/pagamentos.md)
- [Fluxo: Suprimento de Fundos](../fluxos/suprimento_fundos.md)
