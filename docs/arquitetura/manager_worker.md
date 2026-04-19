# Padrão Manager-Worker (CQRS-Lite)

!!! danger "Critical Invariant"
	**Views NUNCA contêm lógica de negócio ou validação.**
	- Panels (`panels.py`): apenas GET, montagem de contexto, sem mutação.
	- Actions (`actions.py`): apenas POST, validação de formulário, roteamento para Services. Nunca renderizam templates.

## Panels (Manager)
- Arquivo: `panels.py`
- Responde apenas a requisições GET.
- Monta contexto de tela.
- **Proibido mutar banco de dados ou chamar lógica de domínio.**

## Actions (Router para Workers)
- Arquivo: `actions.py`
- Responde apenas a POST.
- Valida entrada, chama Service, redireciona.
- **Nunca executa lógica de negócio diretamente.**
- **Nunca renderiza template.**

## Services/Helpers (Worker)
- Diretório: `services/`
- Centralizam TODA mutação, transição de estado e regra de domínio.
- **Devem sempre usar `transaction.atomic()` e locks pessimistas (`select_for_update()`).**
- **Devem crashar imediatamente em caso de dados fiscais inválidos.**

!!! tip
	Este padrão garante rastreabilidade, previsibilidade e compliance regulatório.

## Anti-padrões proibidos

!!! danger "Proibido"
	- Qualquer lógica de negócio em views/actions.
	- Validação de regras em formulários.
	- Mutação de estado sem lock pessimista.
	- Uso de floats em cálculos financeiros.

## APIs JSON (Thin Router)
- Arquivo padrão: `apis.py`.
- Responsabilidade: responder chamadas AJAX/fetch de JavaScript com `JsonResponse`. Nunca renderiza template HTML nem redireciona para páginas.
- Regra: não conter mutações de banco diretamente. Toda mutação deve ser delegada para funções em `helpers.py` ou `services/`.
- Contrato de erro: erros de negócio retornam `JsonResponse` com `status` HTTP adequado (ex.: 400 para entrada inválida, 403 para permissão negada, 404 para objeto não encontrado).
- Quando criar: apenas quando o frontend precisa de uma resposta JSON (formulários via JavaScript, painéis com atualização parcial). Para fluxos de formulário HTML padrão, prefira `actions.py`.
