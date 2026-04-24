# Módulo Fiscal

O módulo `fiscal` centraliza retenções e obrigações acessórias do ciclo de pagamento.

## Responsabilidades

- Cálculo e registro de retenções tributárias.
- Consolidação de dados fiscais por pagamento/lote.
- Preparação de informações para integrações oficiais.

!!! danger "Critical Invariant"
	- **Toda rotina fiscal DEVE usar `decimal.Decimal` para cálculos.**
	- **Qualquer inconsistência ou dado inválido (ex: EFD-Reinf) resulta em crash imediato.**
	- **Todas as mutações são protegidas por `transaction.atomic()` e `select_for_update()`.**

## Integração EFD-Reinf

- Agrupamento de eventos fiscais.
- Geração de lotes para envio.
- Rastreamento de retorno e status de processamento.

## Relação com o fluxo

A etapa fiscal atua como gate para progressão segura até pagamento e contabilização.

## Controles e validações

- Obrigatório informar retenções selecionadas.
- Obrigatório anexar simultaneamente relatório de retenções, guia de recolhimento e comprovante de pagamento.
- Obrigatório informar competência válida no campo `competencia` (normalizado internamente para `YYYY-MM-01`).
- Apenas retenções já agrupadas em processo de pagamento são elegíveis para anexação.

!!! note
	Para detalhes operacionais, consulte [Dicionários Operacionais](../desenvolvedor/dicionarios_operacionais.md).
