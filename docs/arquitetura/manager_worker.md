# Padrão Manager-Worker

## Motivação

Em sistemas de gestão financeira com auditoria obrigatória, misturar apresentação e lógica de negócio na mesma camada cria dois problemas sérios: dificulta o rastreamento de *o que* foi feito e *por quê*, e torna impossível testar regras de domínio de forma isolada. O padrão Manager-Worker resolve isso separando uma requisição HTTP em três responsabilidades distintas que nunca se sobrepõem. Para a visão de interface desse mesmo princípio, veja [Interface Hub-and-Spoke](hub_spoke.md).

## As três camadas

### Panel — o Manager

O arquivo `panels.py` de cada módulo responde exclusivamente a requisições GET. Seu trabalho é reunir informações já existentes no banco e montá-las em um dicionário de contexto para que o template possa renderizar a tela. Um Panel não toma decisões, não valida regras e não altera nenhum dado. É um leitor somente-leitura.

Isso garante que qualquer tela do sistema pode ser recarregada quantas vezes for necessário sem efeitos colaterais — propriedade importante em ambientes com múltiplos usuários simultâneos operando sobre os mesmos processos.

### Action — o Roteador

O arquivo `actions.py` responde exclusivamente a requisições POST. Sua responsabilidade é estreita: validar a entrada via formulário Django e, se válida, delegar a operação ao Service correspondente. Após a execução, a Action redireciona — nunca renderiza um template.

No projeto PaGé, Actions devem usar `@permission_required(..., raise_exception=True)` para RBAC e, quando aplicável, `@require_POST` como primeira barreira de método. Consulte também [Controle de Acesso Contextual](controle_acesso_contextual.md) e [Matriz de Permissões](../governanca/matriz_permissoes.md).

A Action não contém regras de negócio. Ela sabe *quem* deve executar a operação, mas não *como* executá-la. Essa separação permite que a mesma lógica de domínio seja reutilizada por diferentes pontos de entrada (interface web, importação em lote, tarefa agendada) sem duplicação.

### Service/Helper — o Worker

O diretório `services/` de cada módulo concentra toda a lógica que muta estado: transições de status na máquina de processos, cálculos financeiros usando exclusivamente `decimal.Decimal`, validações de elegibilidade, turnpikes (validações de pré-condição que bloqueiam avanço de etapa) e integrações com sistemas externos como EFD-Reinf, isolando os pontos de falha. Para contexto de máquina de estados e turnpikes, veja [Domain Knowledge](domain_knowledge.md).

A camada de services é chamada principalmente pelas Actions após validação de formulário, e também por rotinas de importação/lote/comandos quando necessário. Ela nunca deve ser acionada por templates e não deve depender de `request`. Services não conhecem HTTP, não retornam `HttpResponse` e não fazem renderização. Essa independência permite testá-la de forma isolada sem precisar simular uma requisição web.

#### Garantias de consistência

**`transaction.atomic()`** deve envolver mutações compostas que precisam ter sucesso/falha em bloco (ex.: avançar status + registrar documento + emitir evento de auditoria). Se qualquer etapa falhar, o banco retorna ao estado anterior.

**`select_for_update()`** deve ser aplicado quando houver risco de concorrência em fluxo de leitura-antes-da-escrita sobre os mesmos registros. Não é obrigatório em operações puramente append-only sem disputa de estado.

Erros de domínio são levantados imediatamente como exceções — nunca absorvidos silenciosamente. Um dado fiscal inválido, um processo em estado incompatível ou um valor inconsistente interrompem a operação antes que qualquer dado seja persistido.

## Fronteiras obrigatórias

- Panels: somente leitura + contexto + renderização.
- Actions: validação de entrada, autorização RBAC e roteamento para worker.
- Services/Helpers: regras de negócio e mutação de estado, sem acoplamento a HTTP.
- APIs (`apis.py`): serialização/retorno JSON; mutação delegada para service/helper.

Veja também: [Code Generation: Pattern Matching First](pattern_matching.md).

## Fluxo de uma requisição típica

```
Usuário (POST) → Action
                  ├── form.is_valid()? → não: redirect com mensagem de erro
                  └── sim → Service.executar(dados)
                              ├── select_for_update() + validações
                              ├── mutação no banco
                              └── → Action recebe confirmação → redirect para Hub
```

## APIs JSON

Quando o frontend precisa de respostas estruturadas para interações assíncronas (atualização parcial de painel, formulários via JavaScript), o módulo expõe um arquivo `apis.py`. Sua responsabilidade é exclusivamente serializar e devolver `JsonResponse` — toda mutação é delegada para funções em `helpers.py` ou `services/`, nunca executada diretamente no handler da API.

Erros de negócio retornam status HTTP semântico: `400` para entrada inválida, `403` para permissão negada, `404` para objeto não encontrado. Para fluxos de formulário HTML padrão, o caminho correto continua sendo `actions.py`. Em todos os casos, preserve a rastreabilidade definida em [Trilha de Auditoria](../governanca/trilha_auditoria.md).
