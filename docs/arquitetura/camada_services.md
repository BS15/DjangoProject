# Camada de Services

Toda lógica de negócio com efeito de persistência deve residir em `services/` (ou helpers equivalentes do domínio).

## Responsabilidades da camada
- Aplicar regras de elegibilidade e turnpikes.
- Executar transições de estado da máquina de processos.
- Registrar eventos relevantes para auditoria.
- Encapsular integrações e validações de consistência.

## O que não deve ficar em views
- Decisão de transição de etapa.
- Cálculo fiscal complexo.
- Alterações de múltiplos registros sem orquestração de serviço.

## Benefícios arquiteturais
- Coesão de domínio.
- Facilidade de testes unitários e de integração.
- Evolução segura em cenários regulatórios.
