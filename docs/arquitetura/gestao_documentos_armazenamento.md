# Gestão de Documentos e Armazenamento

Este documento descreve como o PaGé gerencia anexos/documentos no backend: validação, persistência no storage, convenção de pastas, acesso seguro e comportamento no sistema de arquivos.

## 1. Visão geral técnica

No Django, os anexos são armazenados em `FileField` e o banco salva apenas o caminho relativo do arquivo (por exemplo: `pagamentos/2026/proc_123/nota.pdf`).

No PaGé, o fluxo padrão é:

1. Upload via formulário (`multipart/form-data`) em uma `action` (POST).
2. Validação de conteúdo binário por MIME real (`magic bytes`) em `validar_arquivo_seguro`.
3. Definição do caminho lógico por `upload_to` (na maioria dos casos via `caminho_documento`).
4. Persistência do arquivo no storage ativo e do caminho relativo no banco.
5. Leitura/preview/download preferencialmente por endpoint seguro contextual.

## 2. Onde os arquivos ficam fisicamente

Configuração central em `settings.py`:

- `MEDIA_URL = "/media/"`
- `MEDIA_ROOT = BASE_DIR / "media"`

Em desenvolvimento local, os arquivos ficam no diretório do projeto:

- `./media/<caminho_relativo_salvo_no_campo>`

Em Docker Compose (ambiente padrão do projeto), o caminho efetivo dentro dos containers é:

- Web/Nginx: `/app/media/`
- Volume nomeado: `media_volume`

Ou seja: o banco continua guardando caminho relativo, e o arquivo real fica materializado no volume Docker.

## 3. Convenção de pastas (upload_to)

### 3.1 Convenção canônica compartilhada: `caminho_documento`

A maior parte dos documentos usa `commons.shared.storage_utils.caminho_documento`.

Ele sanitiza o nome e organiza por contexto de negócio:

- Processo (`instance.processo`): `pagamentos/<ano>/proc_<id>/<arquivo>`
- Prestação de diária (`instance.prestacao`): `verbasindenizatorias/prestacoes/prestacao_<id>/<arquivo>`
- Diária: `verbasindenizatorias/diarias/diaria_<id>/<arquivo>`
- Reembolso: `verbasindenizatorias/reembolsos/reembolso_<id>/<arquivo>`
- Jeton: `verbasindenizatorias/jetons/jeton_<id>/<arquivo>`
- Auxílio: `verbasindenizatorias/auxilios/auxilio_<id>/<arquivo>`
- Despesa de suprimento: `suprimentosdefundos/suprimento_<id>/despesas/<arquivo>`
- Suprimento (demais documentos): `suprimentosdefundos/suprimento_<id>/<arquivo>`
- Fallback: `documentos_avulsos/<arquivo>`

### 3.2 Pastas especiais fora do helper canônico

Alguns modelos usam `upload_to` fixo/específico:

- Consolidado final do processo: `processos_arquivados/`
- Devoluções processuais: `devolucoes/`
- Assinatura eletrônica (rascunho): `assinaturas_rascunho/`
- Assinatura eletrônica (assinado): `documentos_assinados/`
- Fiscal (pagamento de imposto): `fiscal/pagamentos_impostos/<YYYY-MM>/<arquivo>`
- Temporários de split PDF: `temp/`

## 4. Higienização de nome de arquivo e prevenção de path traversal

Antes de montar o caminho, o sistema aplica `_safe_filename`:

- remove diretórios embutidos no nome enviado (usa basename POSIX);
- normaliza para nome válido via `get_valid_filename`;
- aplica fallback para `arquivo` quando necessário.

Com isso, um nome malicioso como `../../etc/passwd` nao cria caminhos fora do storage.

## 5. Validação de tipo de arquivo (conteúdo real)

O validador compartilhado `validar_arquivo_seguro` aceita apenas:

- `application/pdf`
- `image/jpeg`
- `image/png`

A validação e baseada em assinatura binaria (magic bytes), nao apenas extensao.

## 6. Como o acesso aos arquivos e controlado

O sistema possui endpoint dedicado de download seguro:

- URL: `/documentos/secure/<tipo_documento>/<documento_id>/`
- View: `pagamentos.views.security.download_arquivo_seguro`

Comportamento:

1. Resolve o documento pelo tipo (`processo`, `fiscal`, `suprimento`, `verba_*`, etc.).
2. Valida autorizacao contextual (ownership/perfil), com bypass apenas para superuser/auditoria.
3. Registra trilha de acesso em `RegistroAcessoArquivoProcessual`.
4. Retorna `FileResponse` com o arquivo.

Na maior parte das telas de negocio, os links de visualizacao/download usam esse endpoint seguro.

## 7. Exposição de /media no Nginx

No `nginx.conf`, existe mapeamento direto:

- `location /media/ { alias /app/media/; }`

Isso permite servir arquivos por URL direta de media quando um link usa `arquivo.url`.

Hoje, o uso predominante da UI para documentos processuais e de verbas e via rota segura. Ainda assim, pontos fora do fluxo principal podem usar URL direta de media (por exemplo, tela de assinaturas), o que bypassa validacoes contextuais da view segura.

## 8. Limpeza de arquivos (delete/substituição)

### 8.1 Coberto por sinais/modelos

Para documentos de processo e documentos de verbas indenizatorias, existe limpeza explicita de arquivo anterior/fisico via `_delete_file` em sinais (`pre_save`, `post_delete`) quando aplicavel.

### 8.2 Pontos de atenção

Modelos com `FileField` fora desses sinais dependem do comportamento de sobrescrita/exclusão do próprio fluxo de negócio. Em revisoes futuras, vale padronizar a mesma estratégia de cleanup para todos os agregados documentais.

## 9. Compatibilidade com storages nao-locais

A camada de serviços evita depender de caminho local de arquivo (`.path`) para operações de leitura/merge.

Exemplo: consolidação de PDFs do processo lê por `doc.arquivo.open("rb")` + `storage.exists(...)`, mantendo compatibilidade com storage remoto (S3, GCS, etc.).

## 10. Resumo operacional

- O banco guarda caminho relativo; o arquivo vive no storage (`MEDIA_ROOT`/volume).
- A convenção de pastas e majoritariamente centralizada em `caminho_documento`.
- O acesso seguro existe e é auditado por registro de acesso.
- Há exposição HTTP de `/media/` no Nginx para links diretos.
- A validação de upload é por MIME real e bloqueia formatos fora de PDF/JPEG/PNG.
