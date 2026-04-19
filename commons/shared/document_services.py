"""Serviços compartilhados para operações documentais reutilizáveis."""

from django.db.models import Max


def obter_proxima_ordem_documento(manager_documentos):
    """Retorna a próxima ordem sequencial para um manager relacionado."""
    return (manager_documentos.aggregate(max_ordem=Max("ordem"))["max_ordem"] or 0) + 1


def obter_ou_criar_tipo_documento(nome_tipo_documento, tipo_pagamento=None):
    """Resolve um tipo documental por nome, com fallback para tipo geral."""
    from pagamentos.domain_models import TiposDocumento as TiposDeDocumento

    if tipo_pagamento is not None:
        tipo_especifico = TiposDeDocumento.objects.filter(
            tipo_de_documento__iexact=nome_tipo_documento,
            tipo_de_pagamento=tipo_pagamento,
        ).first()
        if tipo_especifico:
            return tipo_especifico

    tipo_geral = TiposDeDocumento.objects.filter(
        tipo_de_documento__iexact=nome_tipo_documento,
        tipo_de_pagamento__isnull=True,
    ).first()
    if tipo_geral:
        return tipo_geral

    return TiposDeDocumento.objects.create(
        tipo_de_documento=nome_tipo_documento,
        tipo_de_pagamento=tipo_pagamento,
    )