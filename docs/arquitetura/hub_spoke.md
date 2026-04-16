# Interface Hub-and-Spoke

A experiência funcional do PaGé evita páginas monolíticas de edição.

## Hub (Painel de Comando)
- Tela de detalhe da entidade, predominantemente de leitura.
- Consolida status, documentos, histórico e próximos passos.

## Spokes (Tarefas Isoladas)
- Endpoints de ação única (ex.: anexar documento, aprovar etapa, registrar retenção).
- Após execução, sempre retornam ao Hub por redirecionamento.

## Resultado esperado
- Menor complexidade por tela.
- Fluxos mais previsíveis para o usuário.
- Menor risco de inconsistência transacional.
