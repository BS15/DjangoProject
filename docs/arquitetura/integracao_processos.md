# Integração de Processos (Pagamentos, Verbas e Suprimentos)

Esta página documenta os pontos de integração arquitetural entre o módulo central de **Pagamentos** e os domínios satélites de **Verbas Indenizatórias** (incluindo Diárias) e **Suprimentos de Fundos**.

## Padrão Arquitetural: Centralização em `processo_integration.py`

De acordo com as diretrizes do ERP, todas as funções que realizam comunicação cruzada (cross-app) devem estar centralizadas e contidas estritamente no nível da camada de `services/` de cada app, especificamente nos arquivos `processo_integration.py`.

A validação do código atual confirma que esse padrão **está sendo seguido**.

O orquestrador destas integrações localiza-se em `apps/pagamentos/services/integracoes/processo_relacionados.py`. Ele utiliza carregamento sob demanda (`import_string` do Django) para evitar dependências circulares, invocando os devidos hooks expostos pelos domínios satélites.

### 1. Pagamentos e Verbas Indenizatórias (Diárias, Reembolsos, etc.)
- **Caminho:** `apps/verbas_indenizatorias/services/processo_integration.py`
- Os artefatos e as mudanças de status transitam de maneira reflexiva entre a diária e o pagamento.

**Pontos de Contato Constatados no Serviço:**
1. `criar_processo_e_vincular_verbas`: Disparado para criar um Processo base englobando lotes de verbas e avançando o status para "ENVIADA PARA PAGAMENTO", também gerando o respectivo rascunho em PDF (PCD).
2. `gerar_documentos_relacionados_por_transicao`: Disparado pelo pagamentos quando o processo se torna "PAGO". Ele gera automaticamente os Comprovantes e Recibos (PCD, Recibos de Jeton, Reembolsos).
3. `sincronizar_relacoes_apos_transicao`: Disparado assim que a tramitação do processo é efetivamente aprovada/paga. Reflete o status "PAGA" individualmente nas Diárias, Reembolsos, e Auxílios acoplados.

### 2. Pagamentos e Suprimentos de Fundos
- **Caminho:** `apps/suprimentos/services/processo_integration.py`
- Mantém o encapsulamento, centralizando os ganchos do ciclo de vida que o suprimento tem com o seu respectivo processo.

**Pontos de Contato Constatados no Serviço:**
1. `criar_processo_para_suprimento`: Inicia uma transação atômica que reflete a criação da intenção de suprimento de fundos para o processo que definirá a destinação e pagamento, utilizando instâncias como "A EMPENHAR".
2. `gerar_documentos_relacionados_por_transicao`: Em conformidade com a assinatura dos serviços de integração de documento, mas não atua ativamente, já que no contexto de suprimentos não existem apêndices extras gerados pela base em transições padrão.
3. `sincronizar_relacoes_apos_transicao`: Semelhante à documentação anterior, mantém conformidade garantindo o acoplamento das fases, mesmo que internamente a lógica complexa de estado permaneça no próprio domínio de suprimento.

## Benefícios Desta Abordagem
* O uso restrito do arquivo especial provê um mapa documentado de imediato.
* Permite refatorações locais sem quebrar outras áreas da arquitetura monolítica fatiada.
* Facilita os testes simulados para eventos transnacionais em domínios isolados.
