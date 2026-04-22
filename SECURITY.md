# Política de Segurança

## Escopo

O PaGé é um sistema de backoffice financeiro e administrativo para uso interno por entidades de administração pública brasileira. Vulnerabilidades que afetam a confidencialidade, integridade ou disponibilidade de dados financeiros e de pagamentos são consideradas críticas, independentemente da fase de desenvolvimento.

---

## Como Reportar uma Vulnerabilidade

**Não abra issues públicas para relatar vulnerabilidades de segurança.**

Reporte de forma privada através do canal interno da equipe (e-mail ou sistema de gestão interno — contate o responsável técnico do projeto para obter o canal correto). Inclua:

1. Descrição detalhada da vulnerabilidade.
2. Passos para reproduzir.
3. Impacto potencial.
4. Versão/branch afetado.

### SLA de Resposta

| Severidade | Confirmação | Patch |
|---|---|---|
| Crítica | 48 horas | 7 dias |
| Alta | 72 horas | 14 dias |
| Média/Baixa | 5 dias úteis | Próximo sprint |

---

## Controles de Segurança Implementados

### Autenticação Global

Todas as rotas da aplicação são protegidas pelo `GlobalLoginRequiredMiddleware`. Não existe nenhum endpoint operacional acessível sem autenticação prévia.

### Controle de Acesso (RBAC)

Endpoints protegidos com `@permission_required('app_label.codename', raise_exception=True)`. Em caso de acesso não autorizado, a aplicação retorna HTTP 403 — nunca redireciona para o login, evitando vazamento de existência de recursos. Consulte a [Matriz de Permissões](docs/governanca/matriz_permissoes.md) para o mapeamento completo de codenames por domínio.

### Validação de Uploads

Arquivos enviados são validados por magic bytes (não apenas pela extensão). Apenas PDF, JPEG e PNG são aceitos. O tamanho máximo configurado no Nginx é de 20 MB.

### Trilha de Auditoria Imutável

Todas as mutações em modelos críticos são auditadas via `django-simple-history`. Registros não são deletados — exceções de fluxo usam modelos `Contingência` ou `Devolução`.

### Integridade Transacional

Mutações financeiras são executadas dentro de `transaction.atomic()` com `select_for_update()` para garantir consistência e evitar race conditions.

### Proteções Django Padrão

- CSRF obrigatório em todos os formulários POST.
- `SECURE_SSL_REDIRECT` habilitado em produção (`DEBUG=False`).
- `X-Content-Type-Options: nosniff` nos responses de media.

---

## Fora de Escopo

- Engenharia social e phishing direcionado a usuários.
- Vulnerabilidades em infraestrutura/hospedagem fora do controle da aplicação.
- Problemas de segurança em dependências de terceiros sem vetor de exploração demonstrado no contexto do PaGé.
