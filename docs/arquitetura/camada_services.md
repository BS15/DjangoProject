# Camada de Services

## Por que uma camada dedicada

Em um sistema de gestão financeira pública, toda mutação de dados precisa ser rastreável, atômica e auditável. Distribuir essa lógica entre views, formulários e models ad-hoc torna impossível garantir essas propriedades de forma consistente. A camada de services existe para centralizar em um único lugar todas as operações que alteram estado — tornando cada uma delas testável de forma isolada e fácil de auditar.

## O que vive aqui

O diretório `services/` de cada módulo agrupa as funções e classes responsáveis por:

- Avaliar elegibilidade e aplicar turnpikes (validações de pré-condição que bloqueiam avanço de etapa).
- Executar transições de status na máquina de processos, garantindo que cada salto respeite o grafo de estados válidos.
- Registrar eventos relevantes para auditoria via `django-simple-history`.
- Encapsular integrações com sistemas externos (EFD-Reinf, sistemas orçamentários), isolando os pontos de falha.
- Realizar cálculos financeiros usando exclusivamente `decimal.Decimal` — o tipo `float` não é utilizado em nenhum cálculo monetário do sistema.

## Garantias de consistência

Toda operação em `services/` que altera dados financeiros ou de status envolve dois mecanismos obrigatórios:

**`transaction.atomic()`** garante que um conjunto de operações relacionadas (ex.: avançar status + registrar documento + emitir evento de auditoria) seja tratado como uma unidade indivisível. Se qualquer etapa falhar, o banco retorna ao estado anterior.

**`select_for_update()`** adquire um lock pessimista sobre os registros alvos antes de qualquer leitura que preceda uma escrita. Isso elimina race conditions em cenários onde múltiplos usuários operam sobre o mesmo processo simultaneamente.

Erros de domínio são levantados imediatamente como exceções — nunca absorvidos silenciosamente. Um dado fiscal inválido, um processo em estado incompatível, ou um valor inconsistente interrompem a operação antes que qualquer dado seja persistido.

## Relação com as outras camadas

A camada de services é chamada pela [camada de Actions](manager_worker.md) após validação de formulário, e nunca diretamente por templates ou models. Ela não conhece HTTP, não retorna `HttpResponse`, e não tem acesso a `request`. Essa independência é o que permite testá-la com `pytest` sem precisar simular uma requisição web.

Para uma descrição de como Actions roteiam para Services, consulte [Padrão Manager-Worker](manager_worker.md).
