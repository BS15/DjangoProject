_SOLICITACAO_LABELS = {
    "diaria": "Diária",
    "reembolso": "Reembolso",
    "jeton": "Jeton",
    "auxilio": "Auxílio",
}


def resumo_solicitacao(tipo_verba, solicitacao):
    """Normaliza dados de exibição da solicitação para fila e tela de revisão."""
    if tipo_verba == "diaria":
        data_saida = solicitacao.data_saida.strftime("%d/%m/%Y") if solicitacao.data_saida else "-"
        data_retorno = solicitacao.data_retorno.strftime("%d/%m/%Y") if solicitacao.data_retorno else "-"
        referencia = f"{solicitacao.numero_siscac or solicitacao.id} — {data_saida} a {data_retorno}"
    elif tipo_verba == "jeton":
        referencia = f"{solicitacao.numero_sequencial} — Reunião {solicitacao.reuniao}"
    elif tipo_verba == "auxilio":
        referencia = f"{solicitacao.numero_sequencial} — {solicitacao.objetivo or 'Representação'}"
    else:
        referencia = f"{solicitacao.numero_sequencial} — {solicitacao.cidade_origem} → {solicitacao.cidade_destino}"

    return {
        "id": solicitacao.id,
        "tipo_verba": tipo_verba,
        "tipo_label": _SOLICITACAO_LABELS[tipo_verba],
        "beneficiario_nome": getattr(solicitacao.beneficiario, "nome", "-"),
        "status": solicitacao.status,
        "referencia": referencia,
        "valor_total": solicitacao.valor_total,
    }
