import unicodedata


CIDADES_RETENCAO = [
    "BALNEARIO CAMBORIU",
    "BLUMENAU",
    "CHAPECO",
    "CRICIUMA",
    "FLORIANOPOLIS",
    "JOINVILLE",
    "LAGES",
    "PALHOCA",
    "SAO JOSE",
]


def _normalizar_cidade(nome):
    """Remove acentos e converte para uppercase."""
    if not nome:
        return ""
    nfkd = unicodedata.normalize("NFKD", nome)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acento.upper()


def process_invoice_taxes(extracted_json):
    """
    Recebe o JSON extraído pela IA (Etapa 1) e aplica as regras de negócio
    determinísticas (Etapas 2 a 5), retornando o dicionário padronizado
    da Etapa 6.
    """
    retencoes = []
    alertas = []

    valor_bruto = extracted_json.get("valor_bruto") or 0.0
    valor_liquido = extracted_json.get("valor_liquido") or 0.0
    optante_simples = extracted_json.get("optante_simples_nacional", False)
    impostos_federais = extracted_json.get("impostos_federais") or {}
    justificativa = extracted_json.get("justificativa_isencao_federal")
    iss = extracted_json.get("iss") or {}
    inss_destacado = extracted_json.get("inss_destacado") or 0.0

    # ── Etapa 2: Impostos Federais ──────────────────────────────────────────
    if not optante_simples:
        ir = impostos_federais.get("ir") or 0.0
        pis = impostos_federais.get("pis") or 0.0
        cofins = impostos_federais.get("cofins") or 0.0
        csll = impostos_federais.get("csll") or 0.0
        soma_federais = ir + pis + cofins + csll

        if soma_federais > 0:
            if valor_bruto > 0:
                aliquota_efetiva = round((soma_federais / valor_bruto) * 100, 2)
            else:
                aliquota_efetiva = 0.0

            if 9.40 <= aliquota_efetiva <= 9.50:
                retencoes.append({
                    "codigo": "6190",
                    "valor": soma_federais,
                    "descricao": "IR/PIS/COFINS/CSLL",
                })
            elif 5.80 <= aliquota_efetiva <= 5.90:
                retencoes.append({
                    "codigo": "6147",
                    "valor": soma_federais,
                    "descricao": "IR/PIS/COFINS/CSLL",
                })
        else:
            if not justificativa:
                alertas.append(
                    "Fornecedor não é Simples Nacional e não destacou impostos federais"
                    " nem justificativa legal. Solicitar correção da Nota Fiscal."
                )

    # ── Etapa 3: ISS Municipal ──────────────────────────────────────────────
    iss_valor = iss.get("valor_destacado") or 0.0
    if iss_valor > 0:
        local = iss.get("local_prestacao_servico") or ""
        local_normalizado = _normalizar_cidade(local)

        if local_normalizado in CIDADES_RETENCAO:
            retencoes.append({
                "codigo": "ISS_RETIDO",
                "valor": iss_valor,
                "descricao": "ISS Município Conveniado",
            })
        else:
            alertas.append(
                "ISS destacado e descontado para cidade não conveniada."
                " Solicitar correção da Nota Fiscal para que o ISS não seja retido."
            )

    # ── Etapa 4: INSS ───────────────────────────────────────────────────────
    if inss_destacado > 0:
        retencoes.append({
            "codigo": "INSS_RETIDO",
            "valor": inss_destacado,
            "descricao": "Retenção Previdenciária",
        })
        alertas.append(
            f"Atenção: Retenção de INSS identificada no valor de R$ {inss_destacado:.2f}."
        )

    # ── Etapa 5: Conferência Matemática ─────────────────────────────────────
    total_retido = sum(r["valor"] for r in retencoes)
    valor_calculado = valor_liquido + total_retido
    diferenca = abs(valor_bruto - valor_calculado)

    sucesso_matematico = diferenca <= 0.05
    if not sucesso_matematico:
        alertas.append(
            f"Erro de integridade matemática na nota. Valor Bruto"
            f" (R$ {valor_bruto:.2f}) diverge da soma do Líquido + Retenções"
            f" (R$ {valor_calculado:.2f}). Verificar descontos não informados."
        )

    # ── Etapa 6: Saída Padronizada ──────────────────────────────────────────
    return {
        "sucesso_matematico": sucesso_matematico,
        "valor_bruto_identificado": valor_bruto,
        "valor_liquido_identificado": valor_liquido,
        "retencoes_a_processar": retencoes,
        "alertas_usuario": alertas,
    }
