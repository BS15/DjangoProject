# Padrão Manager-Worker

## Motivação

Em sistemas de gestão financeira com auditoria obrigatória, misturar apresentação e lógica de negócio na mesma camada cria dois problemas sérios: dificulta o rastreamento de *o que* foi feito e *por quê*, e torna impossível testar regras de domínio de forma isolada. O padrão Manager-Worker resolve isso separando uma requisição HTTP em três responsabilidades distintas que nunca se sobrepõem.

## As três camadas

### Panel — o Manager

O arquivo `panels.py` de cada módulo responde exclusivamente a requisições GET. Seu trabalho é reunir informações já existentes no banco e montá-las em um dicionário de contexto para que o template possa renderizar a tela. Um Panel não toma decisões, não valida regras e não altera nenhum dado. É um leitor somente-leitura.

Isso garante que qualquer tela do sistema pode ser recarregada quantas vezes for necessário sem efeitos colaterais — propriedade importante em ambientes com múltiplos usuários simultâneos operando sobre os mesmos processos.

### Action — o Roteador

O arquivo `actions.py` responde exclusivamente a requisições POST. Sua responsabilidade é estreita: validar a entrada via formulário Django e, se válida, delegar a operação ao Service correspondente. Após a execução, a Action redireciona — nunca renderiza um template.

A Action não contém regras de negócio. Ela sabe *quem* deve executar a operação, mas não *como* executá-la. Essa separação permite que a mesma lógica de domínio seja reutilizada por diferentes pontos de entrada (interface web, importação em lote, tarefa agendada) sem duplicação.

### Service/Helper — o Worker

O diretório `services/` concentra toda a lógica que muta estado. É aqui que vivem as transições de status, os cálculos financeiros, as validações de elegibilidade e as integrações com sistemas externos. Cada operação que altera dados financeiros ou de status opera dentro de um `transaction.atomic()` com `select_for_update()`, garantindo consistência em acesso concorrente.

Erros de domínio (dados fiscais inválidos, processo em estado incompatível, valor inconsistente) são levantados imediatamente como exceções — nunca silenciados ou compensados parcialmente.

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

Erros de negócio retornam status HTTP semântico: `400` para entrada inválida, `403` para permissão negada, `404` para objeto não encontrado. Para fluxos de formulário HTML padrão, o caminho correto continua sendo `actions.py`.
