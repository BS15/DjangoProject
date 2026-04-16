# Matriz de Permissões (RBAC)

O PaGé adota controle de acesso por permissões explícitas por domínio funcional.

## Diretriz técnica
- Proteção de endpoints com `@permission_required('app_label.permission_name', raise_exception=True)`.
- Sem uso de atalho por grupos customizados na camada de view.
- Sem dependência operacional do Django Admin para usuários finais.

## Objetivo de negócio
- Garantir segregação de funções.
- Evitar aprovações indevidas.
- Permitir rastreabilidade por perfil e por ação executada.

## Estrutura recomendada de matriz
- Ação operacional.
- Permissão requerida.
- Perfis autorizados.
- Risco mitigado.
