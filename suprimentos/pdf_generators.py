"""Geradores de PDF para documentos de suprimentos de fundos."""

from commons.shared.pdf_tools import BasePDFDocument, _draw_wrapped_text


class ReciboSuprimentoDocument(BasePDFDocument):
    """Gera PDF de recibo para suprimento de fundos."""

    def draw_content(self):
        """Desenha corpo do recibo de suprimento."""
        suprimento = self.obj
        c = self.canvas
        page_width = self.page_width

        valor_formatado = self._formatar_moeda(suprimento.valor_liquido)
        beneficiario = suprimento.suprido
        beneficiario_nome = beneficiario.nome if beneficiario else "N/A"
        beneficiario_cpf = beneficiario.cpf_cnpj if beneficiario else "N/A"

        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(page_width / 2, 620, "RECIBO DE PAGAMENTO")

        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(page_width / 2, 590, "SUPRIMENTO DE FUNDOS")

        declaration = (
            f"Recebi do Conselho Regional de Corretores de Imóveis de Santa Catarina - "
            f"11ª Região (CRECI-SC), a importância líquida de {valor_formatado}, "
            "referente ao pagamento de Suprimento de Fundos."
        )
        margin_left = 72
        text_width = page_width - 2 * margin_left
        _draw_wrapped_text(
            c, declaration, margin_left, 540, text_width,
            font_name="Helvetica", font_size=12,
        )

        c.setFont("Helvetica", 11)
        c.drawString(margin_left, 450, f"Beneficiário / Recebedor: {beneficiario_nome}")
        c.drawString(margin_left, 434, f"CPF / CNPJ: {beneficiario_cpf}")

        sig_x = page_width / 2
        c.line(sig_x - 130, 250, sig_x + 130, 250)
        c.setFont("Helvetica", 11)
        c.drawCentredString(sig_x, 265, beneficiario_nome)
        c.drawCentredString(sig_x, 236, "Assinatura do Recebedor")
        c.drawCentredString(sig_x, 220, "Local e Data: Florianópolis, _____ / _____ / _________")

    def _formatar_moeda(self, valor):
        """Formata valor em moeda brasileira (R$)."""
        from commons.shared.text_tools import format_brl_currency
        return format_brl_currency(valor)


SUPRIMENTOS_DOCUMENT_REGISTRY = {
    "recibo_suprimento": ReciboSuprimentoDocument,
}


__all__ = [
    "ReciboSuprimentoDocument",
    "SUPRIMENTOS_DOCUMENT_REGISTRY",
]