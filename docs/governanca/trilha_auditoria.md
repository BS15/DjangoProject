# Trilha de Auditoria

No contexto de administração pública, o PaGé prioriza integridade histórica e prestação de contas.

## Princípios
- Não exclusão de registros de negócio críticos.
- Registro de histórico de alterações em entidades sensíveis.
- Tratamento de exceções por modelos formais (ex.: [contingência](/negocio/glossario_conselho.md#contingencia), [devolução](/negocio/glossario_conselho.md#devolucao)).

## Auditoria persistente

`django-simple-history` sustenta rastreabilidade de mudanças relevantes em dois níveis:

1. Modelos sensíveis registram histórico a cada criação, alteração ou exclusão relevante.
2. O painel de auditoria consolida históricos de múltiplos modelos em uma visão unificada, com filtros por modelo, tipo de ação, período e usuário.

Arquivos centrais:

- `pagamentos/views/auditing/panels.py` — implementa `auditoria_view`, consolida históricos de modelos financeiros, fiscais e documentais.
- `pagamentos/domain_models/suporte.py` — define `RegistroAcessoArquivo`, `Contingencia`, `Devolucao` e `AssinaturaAutentique` com histórico.
- Modelos críticos em múltiplos apps usam `HistoricalRecords()` em entidades como processo, retenção, documentos, suprimentos e assinatura.

## Logging técnico

Módulos sensíveis criam `logger = logging.getLogger(__name__)`. Exceções operacionais são registradas com `logger.exception(...)`. O sistema devolve feedback funcional ao usuário, mas preserva o detalhe técnico no log sem expô-lo na interface.

Principais pontos de logging:

- `commons/shared/storage_utils.py`
- `verbas_indenizatorias/views/shared/documents.py`
- `pagamentos/views/support/sync/pagamentos.py`
- `pagamentos/views/support/signatures.py`
- `verbas_indenizatorias/services/processo_integration.py`

A decisão de chamar `avancar_status(..., usuario=...)` em vez de atualizar o status diretamente reforça esse compromisso: cada transição é rastreada ao operador que a executou.

## Valor para compliance
- Evidência temporal de decisão e execução.
- Transparência em divergências e correções.
- Redução de risco regulatório e operacional.
