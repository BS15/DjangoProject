# Camada de Services

!!! danger "Critical Invariant"
	**Toda lógica de negócio que muta estado ou persiste dados DEVE residir exclusivamente em `services/` ou helpers de domínio.**
	- Nenhuma regra de negócio, validação, cálculo ou transição de status pode existir em views, actions ou forms.

## Responsabilidades da camada

- Aplicar regras de elegibilidade e turnpikes.
- Executar transições de estado da máquina de processos.
- Registrar eventos relevantes para auditoria.
- Encapsular integrações e validações de consistência.
- **Garantir uso obrigatório de `transaction.atomic()` e `select_for_update()` em toda operação que altere dados financeiros ou de status.**
- **Utilizar sempre `decimal.Decimal` para cálculos monetários. É proibido o uso de `float`.**

## O que NÃO deve ficar em views/actions/forms

!!! danger "Proibido"
	- Qualquer decisão de transição de etapa.
	- Qualquer cálculo fiscal, financeiro ou de elegibilidade.
	- Qualquer alteração de múltiplos registros sem orquestração de serviço.
	- Qualquer validação de negócio (deve estar em `full_clean()` do Model ou Service).
	- Qualquer uso de `update()` direto em QuerySets para mutação de estado.

## Benefícios arquiteturais

- Coesão e isolamento do domínio.
- Testabilidade unitária e de integração real.
- Evolução segura e auditável em cenários regulatórios.
- **Compliance fiscal garantido por crash imediato em dados inválidos.**

!!! note
	Para exemplos de implementação, consulte os workers em `services/` dos módulos principais.
