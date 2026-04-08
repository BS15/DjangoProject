# Relatorio Final - Fechamento de Tratamento de Erros

Data: 2026-04-08
Escopo: pasta `processos/` (runtime, excluindo testes)

## 1) Resultado objetivo do fechamento tecnico

- `except Exception` remanescente fora de testes: 0
- `except: pass` remanescente fora de testes: 0
- Swallow com `pass` fora de testes: 0

Conclusao tecnica: os padroes de captura ampla/silenciosa foram eliminados no escopo alvo.

## 2) Arquivos corrigidos na fase final (narrowing/eliminacao)

- processos/validators.py
- processos/utils/cadastros_import.py
- processos/utils/shared/pdf_tools.py
- processos/utils/verbas/diarias/importacao.py
- processos/models/segments/_fluxo_models.py
- processos/views/fluxo/api_views.py
- processos/views/fluxo/helpers/archival.py
- processos/views/fluxo/helpers/audit_builders.py
- processos/views/fluxo/payment/comprovantes/actions.py
- processos/views/fluxo/pre_payment/cadastro/forms.py
- processos/views/fluxo/pre_payment/empenho/actions.py
- processos/views/verbas/verbas_shared.py
- processos/views/verbas/processo/actions.py
- processos/views/verbas/processo/api.py
- processos/views/verbas/processo/helpers.py
- processos/views/verbas/tipos/diarias/forms.py
- processos/views/verbas/tipos/diarias/signatures.py
- processos/views/suprimentos/cadastro/forms.py
- processos/views/suprimentos/prestacao_contas/actions.py
- processos/views/sistemas_auxiliares/assinaturas.py
- processos/views/sistemas_auxiliares/sync/diarias.py
- processos/views/sistemas_auxiliares/sync/pagamentos.py

## 3) Classificacao dos 39 `return None/False`

### 3.1 Contrato valido de negocio/controle de fluxo (39)

Todos os 39 casos foram classificados como contrato explicito da funcao, sem caracterizar falha tecnica silenciosa.

Distribuicao por arquivo:

- 9 em processos/views/verbas/verbas_shared.py
  - retorno `(None, erro)` e flags booleanas para fluxo de upload opcional e feedback de UI.
- 4 em processos/models/segments/_verbas_models.py
  - ausencia de dados para calculo (ex.: valor unitario/cargo) retorna `None` por contrato de dominio.
- 4 em processos/utils/shared/text_tools.py
  - funcoes utilitarias retornam `False/None` para entradas invalidas/ausentes de forma deterministica.
- 3 em processos/models/segments/_fluxo_models.py
  - sem dados orcamentarios/minimo para registrar documento -> retorno `None` esperado.
- 3 em processos/utils/csv_common.py
  - contrato padronizado `(reader, erro)` retornando `None` no ramo de erro de validacao.
- 3 em processos/views/fluxo/helpers/contingencias.py
  - retorno `(False, mensagem)` para rejeicao negocial explicita da contingencia.
- 3 em processos/views/fluxo/security.py
  - predicados de autorizacao retornam `False` quando acesso nao permitido.
- 2 em processos/views/verbas/processo/helpers.py
  - retorno `None` em invalidez de formulario ou erro ja notificado via `messages`/log.
- 2 em processos/views/signature_access.py
  - helper de ownership retorna `False` quando nao ha vinculo.
- 1 em processos/views/fluxo/pre_payment/cadastro/documentos.py
  - helper de bloqueio por status retorna booleano.
- 1 em processos/views/fluxo/pre_payment/helpers.py
  - contrato de retorno multiplo para roteamento e flag `somente_documentos`.
- 1 em processos/views/fluxo/helpers/workflows.py
  - contrato de retorno multiplo para navegacao de fila.
- 1 em processos/views/fluxo/support/contingencia/helpers.py
  - predicado de permissao por etapa retorna booleano.
- 1 em processos/utils/shared/pdf_tools.py
  - parser de linha retorna `None` quando tipo nao reconhecido.
- 1 em processos/admin.py
  - contrato Django Admin (`has_add_permission`) retorna booleano.

### 3.2 Falha tecnica silenciosa (0)

- Nenhum caso identificado nesta rodada.

## 4) Observacoes

- A eliminacao de capturas amplas foi feita priorizando camadas criticas e pontos de IO/integracao.
- Onde o fluxo de negocio demanda resiliencia de UX, manteve-se retorno controlado com log/mensagem explicita.
- Nao houve alteracao de contratos publicos de funcoes cujo retorno booleano/`None` era intencional.
