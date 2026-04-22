# Funcionalidades Transversais do PaGé

Este documento consolida funcionalidades transversais que já existem no sistema, mas que hoje estão espalhadas entre código-fonte e documentação parcial.

Ele cobre cinco frentes:

- gestão de documentos
- importações
- sincronizações
- operações em lote
- assinaturas via Autentique

## 1. Gestão de Documentos

### O que é

A gestão de documentos é a infraestrutura que recebe, valida, organiza, armazena e vincula arquivos aos objetos de negócio do sistema, como processos, diárias, reembolsos, jetons, auxílios, suprimentos e retenções.

No PaGé, documentos não são um detalhe periférico. Eles são parte do próprio fluxo administrativo: comprovam etapas, habilitam avanços de status, alimentam auditoria e materializam saídas do sistema, como PDFs e anexos finais.

### O que faz e para que serve

Essa feature serve para:

- receber uploads enviados por usuários em formulários e actions
- validar se o arquivo é seguro e está em formato aceito
- decidir onde o arquivo será armazenado no storage
- vincular o arquivo ao objeto correto do domínio
- manter ordenação documental por entidade
- sustentar turnpikes do fluxo, já que várias etapas dependem da presença de anexos obrigatórios
- apoiar auditoria, arquivamento e geração de artefatos finais

### Como funciona

Fluxo operacional típico:

1. A entrada acontece por `request.FILES`, normalmente em actions de edição ou cadastro.
2. O sistema valida o arquivo em dois níveis:
   - validação por tipo real do arquivo com `magic bytes`
   - validação de extensão em alguns fluxos específicos de upload documental
3. O caminho de armazenamento é calculado conforme a entidade dona do arquivo.
4. O documento é persistido em um modelo concreto que reutiliza a base documental compartilhada.
5. A action devolve uma saída compatível com o padrão manager-worker:
   - redirect com `messages`
   - render de tela com erros
   - ou anexação silenciosa em fluxos internos de serviço

Entradas mais comuns:

- arquivos PDF, JPG e PNG
- tipo documental selecionado pelo usuário
- entidade de negócio alvo
- contexto do processo ou da verba

Saídas mais comuns:

- registro documental persistido no banco
- arquivo salvo em storage organizado por domínio
- mensagem de sucesso ou erro para o usuário
- anexos usados em auditoria, arquivamento ou pagamento

### Como se reflete no código

Arquivos centrais:

- `commons/shared/models.py`
  - define `DocumentoBase`, modelo abstrato com `arquivo`, `ordem` e `tipo`
  - padroniza a estrutura documental usada por múltiplos apps

- `commons/shared/storage_utils.py`
  - implementa `caminho_documento`, que resolve o diretório físico conforme a entidade relacionada
  - organiza uploads por áreas como `pagamentos`, `verbasindenizatorias` e `suprimentosdefundos`
  - implementa `_safe_filename`, para impedir nomes com caminhos aninhados acidentais
  - implementa `_delete_file`, para limpeza segura no storage

- `commons/shared/file_validators.py`
  - implementa `validar_arquivo_seguro`
  - usa detecção real de MIME para aceitar apenas PDF, JPEG e PNG
  - reduz risco de arquivos adulterados ou extensões enganosas

- `commons/shared/document_services.py`
  - fornece utilitários reutilizáveis como `obter_proxima_ordem_documento`
  - resolve ou cria tipos documentais com `obter_ou_criar_tipo_documento`

- `verbas_indenizatorias/views/shared/documents.py`
  - concentra workers reutilizáveis de upload no domínio de verbas
  - `_salvar_documento_upload` valida e persiste um anexo retornando `(documento, erro)`
  - `_processar_upload_documento` e `_salvar_verba_com_anexo_opcional` conectam request, persistência e feedback ao usuário

- `fiscal/services/impostos.py`
  - cria anexos documentais automáticos em processos de recolhimento de impostos
  - materializa guia, comprovante e relatório mensal como documentos de pagamento

### Observações arquiteturais

- A feature segue o padrão do projeto: a view recebe a requisição, mas a mutação relevante tende a ficar em helper ou service.
- O storage é orientado por domínio, não por upload genérico. Isso facilita operação, manutenção e rastreabilidade.
- Documentos também são produzidos internamente pelo sistema, não apenas recebidos do usuário. Isso aparece em geração de PCD, relatórios fiscais e consolidado final de arquivamento.

## 2. Funcionalidades de Importação

### O que é

As funcionalidades de importação permitem cadastrar ou preparar dados em lote a partir de arquivos externos, principalmente CSV.

No estado atual do projeto, a importação é usada para alimentar cadastros e operações com menor digitação manual, especialmente em credores, contas fixas e diárias.

### O que faz e para que serve

Essa feature serve para:

- reduzir retrabalho operacional em cadastros repetitivos
- absorver dados vindos de planilhas ou exportações externas
- validar dados antes de persistir em massa
- separar etapas de pré-visualização e confirmação quando o risco operacional é maior

### Como funciona

Há dois padrões principais de importação no projeto.

#### Padrão 1: importação direta com resultado resumido

Usado em credores e contas fixas.

1. O usuário envia um CSV pelo painel de importação.
2. O sistema decodifica o arquivo com fallback de encoding.
3. Cada linha é lida como dicionário.
4. O sistema tenta localizar entidades relacionadas, normalizar campos e criar ou reaproveitar registros.
5. O retorno é um resumo com:
   - quantidade de sucessos
   - lista de erros por linha

#### Padrão 2: preview antes de confirmação

Usado na importação de diárias.

1. O usuário envia o CSV.
2. O sistema gera uma prévia serializável em sessão.
3. Erros de validação são exibidos sem gravar nada.
4. Só após confirmação explícita os objetos são criados.

Entradas típicas:

- arquivo CSV
- colunas padronizadas por template
- dados referenciais já existentes no banco, como credores

Saídas típicas:

- resumo de importação
- preview temporário em sessão
- objetos criados em lote
- mensagens de erro por linha

### Como se reflete no código

Arquivos centrais:

- `commons/shared/csv_import_utils.py`
  - oferece funções compartilhadas de leitura, decodificação e construção de `DictReader`
  - é a base técnica para vários fluxos de importação

- `credores/imports.py`
  - implementa `painel_importacao_view`
  - implementa `importar_credores_csv`, que cria ou reaproveita `Credor`, `ContasBancarias` e `CargosFuncoes`
  - concentra também o fluxo de download de template de credores

- `pagamentos/views/support/contas_fixas/imports.py`
  - implementa `importar_contas_fixas_csv`
  - cria `ContaFixa` a partir de linhas CSV vinculadas a credores já existentes
  - também fornece template CSV para o usuário

- `verbas_indenizatorias/views/diarias/imports.py`
  - implementa a view `importar_diarias_view`
  - controla as ações de preview, confirmação e cancelamento
  - usa sessão para segurar o lote provisório até a confirmação

- `verbas_indenizatorias/views/diarias/import_services.py`
  - implementa `_parse_diaria_row`, `preview_diarias_lote` e `confirmar_diarias_lote`
  - valida datas, quantidade de diárias, existência do beneficiário e coerência da linha
  - transforma a prévia em objetos `Diaria` no momento da confirmação

### Observações arquiteturais

- Nem toda importação já foi desacoplada em `panels.py` e `actions.py`; parte do legado ainda concentra fluxo numa view específica de importação.
- O padrão mais robusto hoje é o de diárias, porque separa parsing e persistência em duas fases.
- As importações já demonstram uma tendência forte no projeto: primeiro validar e estruturar dados, depois persistir.

## 3. Funcionalidades de Sync

### O que é

As funcionalidades de sync sincronizam o estado interno do PaGé com artefatos ou eventos externos e também propagam efeitos entre domínios internos quando um processo muda de etapa.

Há dois eixos principais:

- sincronização externa, especialmente com relatórios SISCAC
- sincronização interna entre `pagamentos`, `verbas_indenizatorias` e `suprimentos`

### O que faz e para que serve

Essa feature serve para:

- reconciliar pagamentos registrados externamente com processos do sistema
- reduzir divergência entre sistemas auxiliares e o estado interno do backoffice
- propagar mudanças de status do processo para objetos relacionados em outros módulos
- disparar efeitos colaterais controlados quando marcos do fluxo são atingidos

### Como funciona

#### Sync externo de pagamentos SISCAC

1. O usuário acessa o painel de sincronização.
2. Pode enviar um PDF SISCAC para processamento automático ou selecionar pares para sincronização manual.
3. O parser extrai pagamentos do relatório.
4. O sistema concilia cada pagamento com processos internos usando dados como:
   - número de comprovante
   - nota de empenho
   - nome do credor
   - valor líquido
5. O resultado é classificado em:
   - sucessos
   - divergências
   - não encontrados
   - retroativos corrigidos

#### Sync interno após transições

1. Um `Processo` muda de status.
2. Serviços de integração são chamados para propagar efeitos.
3. Cada domínio relacionado atualiza seus itens, gera documentos ou ajusta estados derivados.

Entradas típicas:

- PDF SISCAC
- seleção manual de pares processo x número SISCAC
- transições de status do fluxo principal

Saídas típicas:

- atualização de `n_pagamento_siscac`
- tela com conciliações e divergências
- atualização de status em verbas e suprimentos vinculados
- geração de documentos decorrentes da transição

### Como se reflete no código

Arquivos centrais:

- `pagamentos/views/support/sync/pagamentos.py`
  - implementa `sincronizar_siscac`, `sincronizar_siscac_auto_action` e `sincronizar_siscac_manual_action`
  - implementa `sync_siscac_payments`, núcleo de conciliação entre relatório externo e processos internos

- `pagamentos/utils.py`
  - contém o parser de relatório SISCAC usado na sincronização automática

- `pagamentos/services/integracoes/processo_relacionados.py`
  - centraliza a orquestração cross-domain
  - `sincronizar_relacoes_apos_transicao` delega propagação para módulos satélite
  - `gerar_documentos_relacionados_por_transicao` dispara documentos dependentes do status do processo

- `verbas_indenizatorias/services/processo_integration.py`
  - propaga status de processo pago para diárias, reembolsos, jetons e auxílios
  - cria documentos relacionados e rascunhos de assinatura em fluxos específicos

### Observações arquiteturais

- Sync não significa apenas integração externa. No projeto, também significa coerência entre domínios internos desacoplados.
- A sincronização externa é orientada por reconciliação; a interna é orientada por eventos de transição de status.
- O padrão é conservador: conciliar primeiro, classificar divergências e só depois aplicar mutações controladas.

## 4. Funcionalidades em Lote

### O que é

As funcionalidades em lote permitem aplicar uma mesma ação a vários registros de uma vez, principalmente em painéis operacionais do fluxo financeiro.

São uma peça importante de produtividade no backoffice, especialmente quando o operador precisa mover dezenas de processos entre etapas ou tratar um conjunto de pendências.

### O que faz e para que serve

Essa feature serve para:

- acelerar operações repetitivas
- reduzir cliques em transições de status
- manter consistência operacional ao aplicar a mesma regra a vários itens
- preservar auditoria mesmo quando a operação atinge múltiplos objetos

### Como funciona

Fluxo típico:

1. O usuário seleciona vários IDs em um painel.
2. A action recebe a lista de IDs via `POST`.
3. O sistema filtra quais itens estão no status de origem esperado.
4. Apenas os elegíveis sofrem mutação.
5. A transição é executada em transação atômica.
6. O retorno informa:
   - quantos foram processados
   - quantos foram ignorados
   - se não havia itens elegíveis

Entradas típicas:

- listas de IDs selecionados
- status de origem esperado
- status de destino
- contexto do painel de origem

Saídas típicas:

- atualização em lote de status
- mensagens de sucesso, warning ou erro
- redirect de volta ao painel operacional

### Como se reflete no código

Arquivos centrais:

- `pagamentos/views/helpers/payment_builders.py`
  - implementa `_processar_acao_lote`, helper genérico para ações em lote
  - implementa `_atualizar_status_em_lote`, que itera processo a processo chamando `avancar_status(..., usuario=...)`
  - usa `transaction.atomic` para garantir integridade da operação

- `pagamentos/views/payment/lancamento/actions.py`
  - usa esse padrão para separar processos para lançamento bancário, marcar como lançados e desfazer lançamentos

- `pagamentos/views/support/pendencia/actions.py`
  - aplica o mesmo raciocínio a tratamento de pendências em lote

### Observações arquiteturais

- O sistema evita `update()` cego quando a operação precisa manter trilha e regras de negócio.
- A opção por chamar `avancar_status` individualmente preserva turnpikes, signals e histórico.
- O lote é operacional, mas não sacrifica compliance.

## 5. Assinaturas Autentique

### O que é

As assinaturas Autentique implementam a integração de assinatura eletrônica do sistema com a API da Autentique.

O projeto usa essa feature para produzir um documento interno, registrá-lo como rascunho, enviá-lo à plataforma de assinatura e acompanhar o ciclo de vida do documento assinado.

### O que faz e para que serve

Essa feature serve para:

- gerar rascunhos de documentos que exigem assinatura
- disparar envio eletrônico para a Autentique
- guardar metadados do documento remoto e dos signatários
- expor links de assinatura para o usuário correto
- sustentar fluxos formais como PCD e outros artefatos assináveis

### Como funciona

Fluxo principal:

1. Um documento PDF é gerado pelo sistema ou preparado para assinatura.
2. O serviço cria um registro local em status `RASCUNHO`.
3. O usuário responsável dispara o envio.
4. O cliente de integração chama a API GraphQL da Autentique.
5. O retorno da plataforma alimenta o registro local com:
   - `autentique_id`
   - URL de assinatura
   - dados dos signatários
   - status `PENDENTE`
6. Em etapas posteriores, o sistema pode consultar o status e baixar o PDF assinado.

Entradas típicas:

- bytes do PDF gerado
- tipo documental
- usuário criador
- e-mail do signatário
- token da API via variável de ambiente

Saídas típicas:

- registro `AssinaturaAutentique`
- URL de assinatura
- dados de signatários
- mudança de status do ciclo de assinatura
- arquivo assinado quando a assinatura é concluída

### Como se reflete no código

Arquivos centrais:

- `pagamentos/domain_models/suporte.py`
  - define o modelo `AssinaturaAutentique`
  - guarda vínculo genérico com a entidade relacionada, status, arquivos e metadados da integração

- `commons/shared/signature_services.py`
  - implementa `criar_assinatura_rascunho`
  - implementa `disparar_assinatura_rascunho_com_signatarios`
  - concentra a lógica transversal do ciclo local de assinatura

- `commons/shared/integracoes/autentique.py`
  - implementa o cliente GraphQL da Autentique
  - envia documentos, processa respostas e consulta status para download do assinado

- `pagamentos/views/support/signatures.py`
  - implementa o painel do usuário e a action de disparo
  - aplica controle de permissão operacional no nível de dono do rascunho

- `verbas_indenizatorias/services/processo_integration.py`
  - usa a infraestrutura de assinatura para criar rascunhos de PCD em fluxos de diárias

### Observações arquiteturais

- A integração foi desenhada para ser transversal: o serviço de assinatura não pertence a um único domínio de negócio.
- O registro local é tão importante quanto a chamada externa, porque ele preserva rastreabilidade, permite reprocessamento e desacopla o domínio da API remota.
- O padrão do projeto é primeiro persistir o rascunho local e só depois acionar a integração externa.