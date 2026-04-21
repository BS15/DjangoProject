"""Geradores de PDF para documentos de suprimentos de fundos."""

from commons.shared.pdf_tools import BasePDFDocument, _draw_wrapped_text
from commons.shared.text_tools import format_brl_currency

_SIG_HALF_WIDTH = 130


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


class RelatorioPrestacaoContasSuprimentoDocument(BasePDFDocument):
    """Gera relatório de prestação de contas para suprimento de fundos.

    O documento lista todas as despesas do período, apresenta os totais financeiros,
    inclui declaração de responsabilidade legal (fidedignidade) e linha de assinatura
    com identificação do suprido.
    """

    def draw_content(self):
        """Desenha o relatório de despesas com declaração de fidedignidade."""
        suprimento = self.obj
        c = self.canvas
        width = self.page_width
        height = self.page_height

        margin_left = 70
        margin_right = 70
        text_width = width - margin_left - margin_right

        beneficiario = suprimento.suprido
        beneficiario_nome = _safe_text(getattr(beneficiario, "nome", None), "Não identificado")
        beneficiario_cargo = _safe_text(getattr(beneficiario, "cargo_funcao", None), "Cargo não informado")
        lotacao = _safe_text(getattr(suprimento, "lotacao", None), "Não informada")
        periodo = (
            f"{_format_date(getattr(suprimento, 'inicio_periodo', None))} a "
            f"{_format_date(getattr(suprimento, 'fim_periodo', None))}"
        )
        valor_liberado = suprimento.valor_liquido or 0
        valor_gasto = suprimento.valor_gasto or 0
        saldo = suprimento.saldo_remanescente or 0
        despesas = suprimento.despesas.all().order_by("data", "id")

        y = height - 160

        # --- Título ---
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(width / 2.0, y, "RELATÓRIO DE PRESTAÇÃO DE CONTAS")
        y -= 16
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(width / 2.0, y, "SUPRIMENTO DE FUNDOS")
        y -= 24

        c.setLineWidth(0.5)
        c.line(margin_left, y, width - margin_right, y)
        y -= 18

        # --- Dados do suprimento ---
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin_left, y, "IDENTIFICAÇÃO DO SUPRIMENTO:")
        y -= 14
        c.setFont("Helvetica", 10)
        c.drawString(margin_left, y, f"Suprido(a):          {beneficiario_nome}")
        y -= 13
        c.drawString(margin_left, y, f"Cargo / Função:      {beneficiario_cargo}")
        y -= 13
        c.drawString(margin_left, y, f"Lotação:             {lotacao}")
        y -= 13
        c.drawString(margin_left, y, f"Período de Vigência: {periodo}")
        y -= 13
        c.drawString(margin_left, y, f"Suprimento Nº:       {suprimento.pk}")
        y -= 20

        c.setLineWidth(0.3)
        c.line(margin_left, y, width - margin_right, y)
        y -= 16

        # --- Tabela de despesas ---
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin_left, y, "RELAÇÃO DE DESPESAS REALIZADAS NO PERÍODO:")
        y -= 14

        # Table header
        col_data = margin_left
        col_nf = col_data + 58
        col_est = col_nf + 72
        col_det = col_est + 118
        col_val = width - margin_right - 2

        c.setFont("Helvetica-Bold", 9)
        c.drawString(col_data, y, "Data")
        c.drawString(col_nf, y, "NF / Cupom")
        c.drawString(col_est, y, "Estabelecimento")
        c.drawString(col_det, y, "Descrição")
        c.drawRightString(col_val, y, "Valor (R$)")
        y -= 4
        c.setLineWidth(0.3)
        c.line(margin_left, y, width - margin_right, y)
        y -= 12

        c.setFont("Helvetica", 9)
        for despesa in despesas:
            if y < 160:
                c.showPage()
                y = height - 80
                c.setFont("Helvetica", 9)

            data_str = _format_date(despesa.data, "-")
            nf_str = _safe_text(despesa.nota_fiscal, "-")[:18]
            est_str = _safe_text(despesa.estabelecimento, "-")[:22]
            det_str = _safe_text(despesa.detalhamento, "-")[:28]
            val_str = format_brl_currency(despesa.valor)

            c.drawString(col_data, y, data_str)
            c.drawString(col_nf, y, nf_str)
            c.drawString(col_est, y, est_str)
            c.drawString(col_det, y, det_str)
            c.drawRightString(col_val, y, val_str)
            y -= 13

        if not despesas:
            c.setFont("Helvetica-Oblique", 9)
            c.drawString(margin_left, y, "Nenhuma despesa registrada neste suprimento.")
            y -= 13

        y -= 4
        c.setLineWidth(0.3)
        c.line(margin_left, y, width - margin_right, y)
        y -= 14

        # --- Resumo financeiro ---
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin_left, y, "RESUMO FINANCEIRO:")
        y -= 14
        c.setFont("Helvetica", 10)
        c.drawString(margin_left, y, f"Numerário Liberado:     {format_brl_currency(valor_liberado)}")
        y -= 13
        c.drawString(margin_left, y, f"Total de Despesas:      {format_brl_currency(valor_gasto)}")
        y -= 13
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin_left, y, f"Saldo Remanescente:     {format_brl_currency(saldo)}")
        y -= 22

        c.setLineWidth(0.5)
        c.line(margin_left, y, width - margin_right, y)
        y -= 16

        # --- Declaração de fidedignidade legal ---
        declaracao = (
            "Declaro, para os devidos fins e sob as penas da lei, que as despesas relacionadas neste "
            "relatório foram efetivamente realizadas no interesse do serviço, que os documentos fiscais "
            "que as comprovam são autênticos e íntegros, e que o eventual saldo remanescente foi ou será "
            "devidamente devolvido ao erário, em estrita conformidade com as normas internas e a "
            "legislação vigente aplicável ao regime de suprimento de fundos."
        )
        y = _draw_wrapped_text(
            c,
            declaracao,
            margin_left,
            y,
            text_width,
            font_name="Helvetica",
            font_size=10,
            leading=14,
            justify=True,
        )
        y -= 16

        # --- Linha de assinatura do suprido ---
        sig_y = max(80, y - 30)
        sig_x = width / 2.0

        c.setFont("Helvetica", 9)
        c.drawCentredString(sig_x, sig_y + 26, beneficiario_nome)
        c.drawCentredString(sig_x, sig_y + 14, beneficiario_cargo)
        c.line(sig_x - _SIG_HALF_WIDTH, sig_y, sig_x + _SIG_HALF_WIDTH, sig_y)
        c.drawCentredString(sig_x, sig_y - 12, f"Suprido(a) — {lotacao}")


SUPRIMENTOS_DOCUMENT_REGISTRY = {
    "recibo_suprimento": ReciboSuprimentoDocument,
    "relatorio_prestacao_contas": RelatorioPrestacaoContasSuprimentoDocument,
}


__all__ = [
    "ReciboSuprimentoDocument",
    "RelatorioPrestacaoContasSuprimentoDocument",
    "SUPRIMENTOS_DOCUMENT_REGISTRY",
]