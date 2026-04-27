"""Utilitarios de query e filtro generico para o fluxo financeiro."""


def _obter_campo_ordenacao(request, campos_permitidos, default_ordem="id", default_direcao="desc"):
    """Extrai e formata o campo de ordenacao com base nos parametros GET.

    Garante que apenas colunas mapeadas em `campos_permitidos` sejam usadas.
    Retorna o campo pronto para `order_by`, com prefixo `-` quando descendente.
    """
    ordem = request.GET.get("ordem", default_ordem)
    direcao = request.GET.get("direcao", default_direcao)
    if direcao not in {"asc", "desc"}:
        direcao = default_direcao
    order_field = campos_permitidos.get(ordem, campos_permitidos.get(default_ordem, "id"))
    return f"-{order_field}" if direcao == "desc" else order_field


def _resolver_parametros_ordenacao(request, campos_permitidos, default_ordem="id", default_direcao="desc"):
    """Resolve parâmetros de ordenação já sanitizados para uso em contexto e queryset."""
    ordem = request.GET.get("ordem", default_ordem)
    if ordem not in campos_permitidos:
        ordem = default_ordem

    direcao = request.GET.get("direcao", default_direcao)
    if direcao not in {"asc", "desc"}:
        direcao = default_direcao

    campo = campos_permitidos.get(ordem, campos_permitidos.get(default_ordem, "id"))
    order_field = f"-{campo}" if direcao == "desc" else campo
    return ordem, direcao, order_field


def _aplicar_filtro_por_opcao(queryset, opcao, mapa_filtros):
    """Aplica filtro por opcao com regras mapeadas (kwargs ou callable)."""
    regra = mapa_filtros.get(opcao)
    if not regra:
        return queryset
    if callable(regra):
        return regra(queryset)
    return queryset.filter(**regra)


__all__ = [
    "_obter_campo_ordenacao",
    "_resolver_parametros_ordenacao",
    "_aplicar_filtro_por_opcao",
]
