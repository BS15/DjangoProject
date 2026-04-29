"""Utilitarios compartilhados de ordenacao e filtro para listagens."""


def resolver_parametros_ordenacao(request, campos_permitidos, default_ordem="id", default_direcao="desc"):
    """Resolve parametros de ordenacao sanitizados para contexto e queryset."""
    ordem = request.GET.get("ordem", default_ordem)
    if ordem not in campos_permitidos:
        ordem = default_ordem

    direcao = request.GET.get("direcao", default_direcao)
    if direcao not in {"asc", "desc"}:
        direcao = default_direcao

    campo = campos_permitidos.get(ordem, campos_permitidos.get(default_ordem, "id"))
    order_field = f"-{campo}" if direcao == "desc" else campo
    return ordem, direcao, order_field


def obter_campo_ordenacao(request, campos_permitidos, default_ordem="id", default_direcao="desc"):
    """Retorna apenas o campo pronto para uso em order_by."""
    _, _, order_field = resolver_parametros_ordenacao(
        request,
        campos_permitidos=campos_permitidos,
        default_ordem=default_ordem,
        default_direcao=default_direcao,
    )
    return order_field


def aplicar_filtro_por_opcao(queryset, opcao, mapa_filtros):
    """Aplica filtro por opcao com regras mapeadas (kwargs ou callable)."""
    regra = mapa_filtros.get(opcao)
    if not regra:
        return queryset
    if callable(regra):
        return regra(queryset)
    return queryset.filter(**regra)


__all__ = [
    "resolver_parametros_ordenacao",
    "obter_campo_ordenacao",
    "aplicar_filtro_por_opcao",
]