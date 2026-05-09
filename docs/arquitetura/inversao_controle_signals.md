# Inversão de Controle com Signals (Event-Driven Architecture)

Para manter a integridade do **Monolito Modular** e garantir que o app `pagamentos` e os domínios satélites (`suprimentos`, `verbas_indenizatorias`, etc.) operem de forma desacoplada, o **GeCap** adota o padrão de eventos de domínio utilizando os Signals nativos do Django.

## O Problema que os Signals Resolvem (Anti-Corruption Layer)
Em uma arquitetura sem eventos, é comum que a lógica central (como o cancelamento de pagamentos) importe funções diretamente de módulos satélites ou vice-versa, criando "God Objects" (arquivos inchados que centralizam todo o negócio).

O uso imperativo causava **Vazamento de Padrões (Pattern Bleed)**. Exemplo: Para cancelar uma verba, a view de verbas importava um serviço hard-coded de pagamentos. Se o sistema ganhasse o módulo de *Licitações*, o módulo de pagamentos precisaria ser alterado para conhecer licitações, violando o princípio de *Open-Closed*.

## Padrão Adotado (Message Bus Interno)

A arquitetura resolve esse acoplamento delegando ao emissor a responsabilidade de anunciar ocorrências por meio do Barramento de Eventos.

### 1. O Barramento Base (`commons/shared/signals.py`)
Todos os eventos transversais ficam tipados na app fundacional `commons`. Exemplo:
```python
import django.dispatch

solicitacao_cancelamento_processo = django.dispatch.Signal()
```

### 2. Emissão (Repatriação da Lógica no Domínio Satélite)
As classes satélites são donas das suas próprias lógicas de alteração e encerramento. No caso das Diárias ou Suprimentos, seus próprios serviços de cancelamento atômicos (`apps/suprimentos/services/cancelamentos.py`) validam e alteram internamente seu modelo para "Cancelado".
Em seguida, lançam a mensagem ao barramento:
```python
solicitacao_cancelamento_processo.send(
    sender=suprimento.__class__,
    instance=suprimento,
    processo=suprimento.processo,
    justificativa="Motivo cancelamento...",
    usuario=request.user,
    dados_devolucao={...},
    tipo_cancelamento_relacional="suprimento_fundos",
    kwargs_relacional={"suprimento": suprimento},
)
```

### 3. Recepção Restrita (`apps/pagamentos/receivers.py`)
O sistema financeiro, operando de maneira reativa, escuta esse canal por meio de Receivers conectados durante o boot inicial (`AppConfig.ready()` em `apps/pagamentos/apps.py`).
O receiver reage interceptando o objeto `processo` transmitido. De forma autônoma e transacionada, apropria a etapa de Pagamentos: ele cancela a esteira do fluxo, gera os recibos de devolução sistêmica (`DevolucaoProcessual`) e lança as auditorias sem nunca precisar invadir o escopo do disparador. 

## Benefícios Deste Ajuste

1. **Escalablidade Sem Modificar Regras Existentes:** Qualquer app recém-criado capaz de emitir o Signal será automaticamente compreendido pelo sistema financeiro, sem alterar uma vírgula em `pagamentos`.
2. **Manutenção do Isolamento:** Apps ganham total autonomia para rodar testes atômicos locais em seus bancos de dados isolados.
3. **Limpeza Funcional:** Ajuda a retirar helpers visuais (classes filtrantes, componentes HTML importados entre apps) e lógicas mistas do domínio transacional e reorientá-los para bibliotecas adequadas como o `commons/shared`.