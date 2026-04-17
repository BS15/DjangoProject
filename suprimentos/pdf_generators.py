"""Geradores de PDF para documentos de suprimentos de fundos."""

from commons.shared.pdf_tools import BasePDFDocument, _draw_wrapped_text
from commons.shared.text_tools import format_brl_currency


def _safe_text(value, fallback="Não informado"):
    """Normaliza texto para exibição em PDF."""
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _format_date(value, fallback="Não informado"):
    """Formata data no padrão brasileiro."""
    return value.strftime('%d/%m/%Y') if value else fallback


class ReciboSuprimentoDocument(BasePDFDocument):
    """Gera PDF de recibo para suprimento de fundos."""

    def draw_content(self):
        """Desenha corpo do recibo de suprimento."""
        suprimento = self.obj
        c = self.canvas
        page_width = self.page_width

        valor_formatado = format_brl_currency(suprimento.valor_liquido)
        beneficiario = suprimento.suprido
        beneficiario_nome = _safe_text(beneficiario.nome if beneficiario else None, "N/A")
        beneficiario_cargo = _safe_text(getattr(beneficiario, "cargo_funcao", None) if beneficiario else None, "N/A")
        lotacao = _safe_text(getattr(suprimento, "lotacao", None), "lotação não informada")
        periodo_concessao = (
            f"{_format_date(getattr(suprimento, 'inicio_periodo', None))} a "
            f"{_format_date(getattr(suprimento, 'fim_periodo', None))}"
        )
        prazo_prestacao = _format_date(
            getattr(suprimento, "data_devolucao_saldo", None) or getattr(suprimento, "fim_periodo", None)
        )

        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(page_width / 2, 620, "RECIBO DE PAGAMENTO")

        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(page_width / 2, 590, "SUPRIMENTO DE FUNDOS")

        declaration = (
            f"Recebi do Conselho Regional de Corretores de Imóveis de Santa Catarina - 11ª Região (CRECI-SC), "
            f"a importância líquida de {valor_formatado} para custear despesas de pequeno vulto e pronto pagamento "
            f"da unidade {lotacao}, no período de concessão de {periodo_concessao}, ciente de que devo prestar "
            f"contas até {prazo_prestacao}."
        )
        margin_left = 72
        text_width = page_width - 2 * margin_left
        y = _draw_wrapped_text(
            c, declaration, margin_left, 540, text_width,
            font_name="Helvetica", font_size=12,
            justify=True,
        )

        c.setFont("Helvetica", 11)
        y -= 24
        c.drawString(margin_left, y, f"Suprido: {beneficiario_nome}")
        y -= 16
        c.drawString(margin_left, y, f"Cargo / Função: {beneficiario_cargo}")
        y -= 16
        c.drawString(margin_left, y, f"Lotação: {lotacao}")
        y -= 16
        c.drawString(margin_left, y, f"Período de Concessão: {periodo_concessao}")
        y -= 16
        c.drawString(margin_left, y, f"Prestação de Contas Até: {prazo_prestacao}")

        sig_x = page_width / 2
        c.setFont("Helvetica", 11)
        c.drawCentredString(sig_x, 258, beneficiario_nome)
        c.drawCentredString(sig_x, 244, beneficiario_cargo)
        c.line(sig_x - 130, 232, sig_x + 130, 232)
        c.drawCentredString(sig_x, 218, "Beneficiário(a) Suprido(a)")

SUPRIMENTOS_DOCUMENT_REGISTRY = {
    "recibo_suprimento": ReciboSuprimentoDocument,
}


__all__ = [
    "ReciboSuprimentoDocument",
    "SUPRIMENTOS_DOCUMENT_REGISTRY",
]