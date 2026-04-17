# Módulo Fiscal

O módulo `fiscal` centraliza retenções e obrigações acessórias do ciclo de pagamento.

## Responsabilidades
- Cálculo e registro de retenções tributárias.
- Consolidação de dados fiscais por pagamento/lote.
- Preparação de informações para integrações oficiais.

## Integração EFD-Reinf
- Agrupamento de eventos fiscais.
- Geração de lotes para envio.
- Rastreamento de retorno e status de processamento.

## Relação com o fluxo
A etapa fiscal atua como gate para progressão segura até pagamento e contabilização.

## Fluxo de recolhimento de impostos (com anexação documental)

O domínio fiscal agora contempla explicitamente o ciclo de anexação de guia e comprovante de recolhimento, com geração de relatório mensal consolidado.

Sequência operacional:
1. Seleção de retenções no painel fiscal.
2. Agrupamento das retenções em processo de recolhimento (`agrupar_retencoes_action`).
3. Upload de guia e comprovante com competência (mês/ano).
4. Execução do worker `anexar_guia_comprovante_relatorio_em_processos(...)`.
5. Anexação automática de três documentos por processo de recolhimento:
	- guia de recolhimento de impostos (`ordem=97`)
	- comprovante de recolhimento de impostos (`ordem=98`)
	- relatório mensal de retenções (`ordem=99`)

## Mapeamento Action -> Service (Fiscal)

| Action | Permissão | Worker | Resultado |
|---|---|---|---|
| `agrupar_retencoes_action` | `fiscal.acesso_backoffice` | n/a (orquestração local da action) | cria processo de recolhimento e vincula retenções |
| `anexar_documentos_retencoes_action` | `fiscal.acesso_backoffice` | `anexar_guia_comprovante_relatorio_em_processos(...)` | anexa guia, comprovante e relatório mensal |

## Controles e validações

- Obrigatório informar retenções selecionadas.
- Obrigatório anexar simultaneamente guia e comprovante.
- Obrigatório informar competência válida (`mes_referencia`, `ano_referencia`).
- Apenas retenções já agrupadas em processo de pagamento são elegíveis para anexação.

Para o padrão completo de documentação operacional de actions e workers, consulte o guia [Dicionários Operacionais](../desenvolvedor/dicionarios_operacionais.md).
