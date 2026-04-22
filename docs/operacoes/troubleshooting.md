# Troubleshooting

Tabela de problemas comuns, causas prováveis e ações corretivas.

---

## Problemas de Fluxo Operacional

| Sintoma | Causa Provável | Solução |
|---|---|---|
| Processo não avança de etapa (Turnpike bloqueado) | Documento obrigatório ausente (ex: Nota Fiscal, Documento Orçamentário, guia de imposto) | Acessar o detalhe do processo; verificar a seção de pendências; anexar o documento do tipo exigido e tentar avançar novamente |
| Verba não aparece para agrupamento | Item não está em status `REVISADA` | Operador de contas a pagar deve revisar o item antes do agrupamento |
| Diária não pode ser solicitada | Status ainda em `RASCUNHO` sem dados obrigatórios | Completar o cadastro da diária e utilizar a ação "Solicitar" |
| Suprimento não encerra | Prestação de contas não aprovada | Aprovar a `PrestacaoContasSuprimento` antes de encerrar o suprimento |

---

## Problemas de Permissão

| Sintoma | Causa Provável | Solução |
|---|---|---|
| HTTP 403 ao acessar qualquer ação | Usuário não possui o codename de permissão necessário | Acessar o Django Admin → Grupos → atribuir o grupo correto ao usuário, ou adicionar a permissão individualmente. Consultar a [Matriz de Permissões](../governanca/matriz_permissoes.md) |
| HTTP 403 mesmo sendo superusuário | Improvável — superusuários têm todas as permissões | Verificar se `raise_exception=True` está correto; checar se o usuário está de fato ativo (`is_active=True`) |
| Usuário redireciona para login ao invés de 403 | `raise_exception=False` em algum decorator | Todos os decorators do projeto devem usar `raise_exception=True`; corrigir na view afetada |

---

## Problemas de Upload

| Sintoma | Causa Provável | Solução |
|---|---|---|
| "Tipo de arquivo não permitido" | Arquivo não é PDF, JPEG ou PNG (validado por magic bytes, não pela extensão) | Converter o arquivo para um formato aceito |
| "Arquivo muito grande" / erro 413 do Nginx | Arquivo excede 20 MB | Comprimir o arquivo ou dividir em partes menores |
| Upload aceito mas arquivo não abre | Arquivo corrompido antes do upload | Verificar integridade do arquivo original |

---

## Integrações Externas

| Sintoma | Causa Provável | Solução |
|---|---|---|
| Envio de documento à Autentique falha | `AUTENTIQUE_API_TOKEN` ausente ou inválido no `.env` | Verificar e atualizar o token no `.env`; reiniciar o container `web` |
| Autentique retorna erro de timeout | Indisponibilidade temporária da API externa | Aguardar e tentar novamente; consultar o status da Autentique |
| SISCAC mostra divergências no sync | Número do comprovante bancário não corresponde ao registrado no sistema | Usar a funcionalidade de seleção manual de comprovante na interface de conciliação |
| Transmissão EFD-Reinf falha | Sem conectividade com o servidor da Receita Federal, ou XML malformado | Verificar conectividade de rede; revisar os XMLs gerados em `/reinf/gerar-lotes/` antes de transmitir |

---

## Problemas de Ambiente

| Sintoma | Causa Provável | Solução |
|---|---|---|
| Container `web` reinicia em loop | Erro de configuração no `.env` ou falha na migração | Executar `docker compose logs web` para ver o erro; verificar variáveis obrigatórias |
| Container `db` em `unhealthy` | PostgreSQL não iniciou corretamente | Executar `docker compose logs db`; verificar se as variáveis `POSTGRES_*` estão corretas |
| Arquivos estáticos não carregam (CSS/JS sumindo) | `collectstatic` não foi executado ou volume não montado corretamente | Executar `docker compose exec web python manage.py collectstatic --noinput` |
| `migrate` falha com erro de schema | Mudança incompatível de modelo (pré-V1) | Aplicar o Clean Slate Protocol — ver [Backup e Restore](backup_restore.md) |
| Página retorna 502 Bad Gateway | Container `web` parado ou lento | Verificar `docker compose ps`; reiniciar com `docker compose restart web` |

---

## Problemas de Auditoria

| Sintoma | Causa Provável | Solução |
|---|---|---|
| Histórico de um objeto não aparece | `django-simple-history` não instalado/migrado corretamente | Verificar se as migrações de `simple_history` foram aplicadas |
| Registro deletado acidentalmente | Violação do princípio de imutabilidade | No pré-V1, restaurar via backup. Em produção, usar modelos `Contingência` ou `Devolução` para reverter efeitos sem deletar |
